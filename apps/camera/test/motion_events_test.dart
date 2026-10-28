import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:smart_spectator_camera/core/control/control_client.dart';
import 'package:smart_spectator_camera/core/motion/motion_reporter.dart';
import 'package:smart_spectator_camera/core/pairing/pairing_client.dart';
import 'package:smart_spectator_camera/hub/device_registry.dart';
import 'package:smart_spectator_camera/hub/event_store.dart';
import 'package:smart_spectator_camera/hub/hub_server.dart';

final _jpeg = Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 9, 9, 9, 0xFF, 0xD9]);

/// Camera phone → main phone motion reports over loopback, using the real
/// MotionReporter (camera side) and HubServer + EventStore (main phone side).
void main() {
  late Directory dir;
  late DeviceRegistry registry;
  late EventStore events;
  late HubServer server;
  late HubAddress hub;

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('ss_motion_test');
    registry = DeviceRegistry(store: InMemoryDeviceStore());
    await registry.load();
    events = EventStore(dir: dir);
    await events.load();
    server = HubServer(registry: registry, port: 0, bindAddress: InternetAddress.loopbackIPv4, events: events);
    await server.start();
    hub = HubAddress('127.0.0.1', server.boundPort!);
  });

  tearDown(() async {
    await server.dispose();
    await dir.delete(recursive: true);
  });

  Future<PairingResponse> pair(String deviceId) =>
      PairingClient.pairWithCode(hub: hub, deviceId: deviceId, deviceName: 'Camera $deviceId', code: registry.hubCode);

  test('motion start stores an event with the snapshot, notifies, and end closes it', () async {
    final cam = await pair('dev_a');
    final notified = <CameraEvent>[];
    server.onMotionStarted = (e, _) => notified.add(e);

    final reporter = MotionReporter(hub: hub, deviceToken: cam.deviceToken!);
    final id = await reporter.started(score: 0.12, snapshotJpeg: _jpeg);
    expect(id, isNotNull);
    expect(server.cameras.single.motionActive, isTrue);
    expect(notified.single.id, id);

    final e = events.byId(id!)!;
    expect(e.cameraId, cam.cameraId);
    expect(e.cameraName, 'Camera dev_a');
    expect(events.snapshotOf(e)!.readAsBytesSync(), _jpeg);

    expect(await reporter.ended(eventId: id, peakScore: 0.5), isTrue);
    expect(events.byId(id)!.isOngoing, isFalse);
    expect(events.byId(id)!.peakScore, 0.5);
    expect(server.cameras.single.motionActive, isFalse);
  });

  test('reports need a valid device token', () async {
    final bad = MotionReporter(hub: hub, deviceToken: 'ss_tok_v1_forged');
    expect(await bad.started(score: 0.1), isNull);
    expect(events.events, isEmpty);
  });

  test('a camera cannot end another camera\'s event', () async {
    final a = await pair('dev_a');
    final b = await pair('dev_b');
    final id = await MotionReporter(hub: hub, deviceToken: a.deviceToken!).started(score: 0.1);
    expect(await MotionReporter(hub: hub, deviceToken: b.deviceToken!).ended(eventId: id!, peakScore: 1), isFalse);
    expect(events.byId(id)!.isOngoing, isTrue);
  });

  test('non-JPEG or invalid snapshots are rejected', () async {
    final cam = await pair('dev_a');
    Future<int> post(Object body) async => (await http.post(hub.uri('/api/v1/events/motion'),
            headers: {'Authorization': 'Bearer ${cam.deviceToken}', 'Content-Type': 'application/json'}, body: jsonEncode(body)))
        .statusCode;
    expect(await post({'phase': 'started', 'snapshot_jpeg': base64Encode([1, 2, 3])}), 400);
    expect(await post({'phase': 'started', 'snapshot_jpeg': '%%%'}), 400);
    expect(await post({'phase': 'sideways'}), 422);
    expect(events.events, isEmpty);
  });

  test('motion switched off on the main phone: reports are ignored and the camera is told', () async {
    final cam = await pair('dev_a');
    final commands = StreamController<Map<String, dynamic>>.broadcast();
    final control = ControlClient(
      hubIp: '127.0.0.1',
      hubPort: hub.port,
      deviceId: 'dev_a',
      cameraId: cam.cameraId!,
      deviceToken: cam.deviceToken!,
      onCommand: commands.add,
    );
    final first = commands.stream.first;
    await control.start();
    // On connect the camera receives its current settings.
    expect((await first.timeout(const Duration(seconds: 2)))['action'], 'set_motion');

    final next = commands.stream.firstWhere((c) => c['action'] == 'set_motion');
    await server.updateCameraSettings(cam.cameraId!, const CameraSettings(motionEnabled: false, sensitivity: 0.9));
    final cmd = await next.timeout(const Duration(seconds: 2));
    expect((cmd['enabled'], cmd['sensitivity']), (false, 0.9));

    expect(await MotionReporter(hub: hub, deviceToken: cam.deviceToken!).started(score: 0.3), isNull);
    expect(events.events, isEmpty);
    control.stop();
  });

  test('camera disconnecting mid-motion closes the open event', () async {
    final cam = await pair('dev_a');
    final ws = await WebSocket.connect('ws://127.0.0.1:${hub.port}/api/v1/control/ws?token=${cam.deviceToken}');
    final id = await MotionReporter(hub: hub, deviceToken: cam.deviceToken!).started(score: 0.2);
    await ws.close();
    for (var i = 0; i < 50 && events.byId(id!)!.isOngoing; i++) {
      await Future<void>.delayed(const Duration(milliseconds: 20));
    }
    expect(events.byId(id!)!.isOngoing, isFalse);
    expect(server.cameras.single.motionActive, isFalse);
  });
}
