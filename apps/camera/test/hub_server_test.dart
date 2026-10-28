import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/core/pairing/pairing_client.dart';
import 'package:smart_spectator_camera/core/protocol/packet_encoder.dart';
import 'package:smart_spectator_camera/core/streaming/media_transport.dart';
import 'package:smart_spectator_camera/hub/device_registry.dart';
import 'package:smart_spectator_camera/hub/hub_server.dart';

/// End-to-end over loopback: the real camcorder client code talks to the real
/// main-phone server, exactly as two phones would over Wi-Fi.
void main() {
  late DeviceRegistry registry;
  late HubServer server;
  late int port;
  const host = '127.0.0.1';

  setUp(() async {
    registry = DeviceRegistry(store: InMemoryDeviceStore());
    await registry.load();
    server = HubServer(registry: registry, port: 0, bindAddress: InternetAddress.loopbackIPv4);
    await server.start();
    port = server.boundPort!;
  });

  tearDown(() async => server.dispose());

  Future<PairingResponse> pairCamera(String deviceId) async {
    final req = await PairingClient.requestPairing(hubIp: host, hubPort: port, deviceId: deviceId, deviceName: 'Camera');
    expect(req.success, isTrue, reason: req.errorMessage);
    final pin = registry.pendingPairings.singleWhere((p) => p.deviceId == deviceId).pin;
    return PairingClient.verifyPairing(hubIp: host, hubPort: port, deviceId: deviceId, pin: pin);
  }

  Uint8List videoPacket(int seq, {bool key = false}) => PacketEncoder.encodePacket(
        frameType: key ? PacketEncoder.frameTypeIdr : PacketEncoder.frameTypeP,
        sequenceNumber: seq,
        ptsUs: seq * 33333,
        payload: Uint8List.fromList([0, 0, 0, 1, key ? 0x65 : 0x41, seq & 0xFF]),
      );

  Future<void> waitFor(bool Function() condition) async {
    for (var i = 0; i < 100 && !condition(); i++) {
      await Future<void>.delayed(const Duration(milliseconds: 20));
    }
    expect(condition(), isTrue);
  }

  test('health endpoint identifies the main phone', () async {
    final client = HttpClient();
    final res = await (await client.get(host, port, '/api/v1/health')).close();
    final body = jsonDecode(await utf8.decodeStream(res));
    client.close();
    expect(res.statusCode, 200);
    expect(body['role'], 'main_phone');
  });

  test('the app flow pairs: request code, user reads it, request again, verify', () async {
    // The old PC hub replaced the PIN on every request, so this always failed.
    await PairingClient.requestPairing(hubIp: host, hubPort: port, deviceId: 'dev_cam_1', deviceName: 'Camera');
    final pinShown = registry.pendingPairings.single.pin;
    await PairingClient.requestPairing(hubIp: host, hubPort: port, deviceId: 'dev_cam_1', deviceName: 'Camera');
    final res = await PairingClient.verifyPairing(hubIp: host, hubPort: port, deviceId: 'dev_cam_1', pin: pinShown);
    expect(res.success, isTrue, reason: res.errorMessage);
    expect(res.deviceToken, startsWith('ss_tok_v1_'));
    expect(res.cameraId, startsWith('cam_'));
  });

  test('wrong code is rejected with a readable message', () async {
    await PairingClient.requestPairing(hubIp: host, hubPort: port, deviceId: 'dev_cam_1', deviceName: 'Camera');
    final pin = registry.pendingPairings.single.pin;
    final res = await PairingClient.verifyPairing(
        hubIp: host, hubPort: port, deviceId: 'dev_cam_1', pin: pin == '123456' ? '654321' : '123456');
    expect(res.success, isFalse);
    expect(res.errorMessage, contains('Invalid code'));
  });

  test('camera streams video packets and the main phone counts them', () async {
    final paired = await pairCamera('dev_cam_1');
    final received = <int>[];
    final sub = server.packets.listen((p) => received.add(p.packet.header.sequenceNumber));

    final transport = MediaTransport(hubIp: host, hubPort: port, cameraId: paired.cameraId!, deviceToken: paired.deviceToken!);
    await transport.connect();
    expect(transport.status, TransportStatus.connected);
    for (var i = 0; i < 10; i++) {
      transport.sendPacket(videoPacket(i, key: i == 0));
    }
    await waitFor(() => received.length == 10);

    final link = server.cameras.single;
    expect(link.streaming, isTrue);
    expect(link.packetsReceived, 10);
    expect(link.keyframes, 1);
    expect(link.protocolErrors, 0);

    transport.dispose();
    await waitFor(() => !server.cameras.single.streaming);
    await sub.cancel();
  });

  test('token keeps working after disconnects (reconnect bug fixed)', () async {
    final paired = await pairCamera('dev_cam_1');
    for (var round = 0; round < 3; round++) {
      final control = await WebSocket.connect('ws://$host:$port/api/v1/control/ws?token=${paired.deviceToken}');
      await waitFor(() => server.cameras.single.controlConnected);
      await control.close();
      await waitFor(() => !server.cameras.single.controlConnected);

      final transport = MediaTransport(hubIp: host, hubPort: port, cameraId: paired.cameraId!, deviceToken: paired.deviceToken!);
      await transport.connect();
      expect(transport.status, TransportStatus.connected, reason: 'round $round');
      transport.dispose();
    }
  });

  test('control channel receives telemetry and can send commands', () async {
    final paired = await pairCamera('dev_cam_1');
    final control = await WebSocket.connect('ws://$host:$port/api/v1/control/ws?token=${paired.deviceToken}');
    final inbox = StreamController<String>();
    control.listen((m) => inbox.add(m as String));

    control.add(jsonEncode({'type': 'telemetry_report', 'metrics': {'battery_level_percent': 64.0, 'is_charging': true}}));
    await waitFor(() => server.cameras.single.batteryLevel == 64.0);
    expect(server.cameras.single.isCharging, isTrue);

    expect(server.requestKeyframe(paired.cameraId!), isTrue);
    final cmd = jsonDecode(await inbox.stream.firstWhere((m) => (jsonDecode(m) as Map)['action'] == 'request_idr'));
    expect(cmd['action'], 'request_idr');
    await control.close();
  });

  test('a camera cannot stream as another camera', () async {
    final a = await pairCamera('dev_cam_a');
    final b = await pairCamera('dev_cam_b');
    expect(a.cameraId, isNot(b.cameraId));
    await expectLater(
      WebSocket.connect('ws://$host:$port/api/v1/streams/ingest/${b.cameraId}?token=${a.deviceToken}'),
      throwsA(isA<WebSocketException>()),
    );
  });

  test('missing or invalid tokens are refused', () async {
    await expectLater(WebSocket.connect('ws://$host:$port/api/v1/control/ws'), throwsA(isA<WebSocketException>()));
    await expectLater(
      WebSocket.connect('ws://$host:$port/api/v1/control/ws?token=ss_tok_v1_forged'),
      throwsA(isA<WebSocketException>()),
    );
  });

  test('revoking a streaming camera disconnects it and blocks its token', () async {
    final paired = await pairCamera('dev_cam_1');
    final ingest = await WebSocket.connect(
        'ws://$host:$port/api/v1/streams/ingest/${paired.cameraId}?token=${paired.deviceToken}');
    final closed = Completer<void>();
    ingest.listen((_) {}, onDone: closed.complete);
    await waitFor(() => server.cameras.single.streaming);

    expect(await server.revokeDevice('dev_cam_1'), isTrue);
    await closed.future.timeout(const Duration(seconds: 2));
    expect(server.cameras, isEmpty);
    await expectLater(
      WebSocket.connect('ws://$host:$port/api/v1/control/ws?token=${paired.deviceToken}'),
      throwsA(isA<WebSocketException>()),
    );
  });

  test('malformed packets are counted, not fatal', () async {
    final paired = await pairCamera('dev_cam_1');
    final ingest = await WebSocket.connect(
        'ws://$host:$port/api/v1/streams/ingest/${paired.cameraId}?token=${paired.deviceToken}');
    ingest.add(Uint8List.fromList(List.filled(30, 7)));
    ingest.add(videoPacket(0, key: true));
    await waitFor(() => server.cameras.single.packetsReceived == 1);
    expect(server.cameras.single.protocolErrors, 1);
    await ingest.close();
  });

  test('rejects invalid pairing input', () async {
    final client = HttpClient();
    Future<int> post(String path, Object body) async {
      final req = await client.post(host, port, path);
      req.headers.contentType = ContentType.json;
      req.write(jsonEncode(body));
      return (await req.close()).statusCode;
    }

    expect(await post('/api/v1/devices/pair/request', {'device_id': 'x', 'device_name': 'a'}), 422);
    expect(await post('/api/v1/devices/pair/request', {'device_id': 'dev_ok_1'}), 422);
    expect(await post('/api/v1/devices/pair/verify', {'device_id': 'dev_ok_1', 'verification_code': 'abc'}), 422);
    client.close();
  });
}
