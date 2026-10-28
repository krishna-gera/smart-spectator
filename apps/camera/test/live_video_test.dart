import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/core/control/control_client.dart';
import 'package:smart_spectator_camera/core/pairing/pairing_client.dart';
import 'package:smart_spectator_camera/core/protocol/packet_decoder.dart';
import 'package:smart_spectator_camera/core/protocol/packet_encoder.dart';
import 'package:smart_spectator_camera/core/video/h264_nal.dart';
import 'package:smart_spectator_camera/core/video/live_video_controller.dart';
import 'package:smart_spectator_camera/hub/device_registry.dart';
import 'package:smart_spectator_camera/hub/hub_server.dart';

// Annex-B fragments: SPS(7), PPS(8), IDR slice(5), P slice(1).
const _sps = [0, 0, 0, 1, 0x67, 0x42, 0x00, 0x1f];
const _pps = [0, 0, 0, 1, 0x68, 0xce, 0x3c, 0x80];
const _idr = [0, 0, 0, 1, 0x65, 0x88, 0x84];
const _p = [0, 0, 0, 1, 0x41, 0x9a, 0x02];

Uint8List bytes(List<List<int>> parts) => Uint8List.fromList(parts.expand((e) => e).toList());

CameraPacket cameraPacket(String cameraId, Uint8List payload, {int seq = 0}) {
  final wire = PacketEncoder.encodePacket(
    frameType: H264Nal.types(payload).contains(5) ? PacketEncoder.frameTypeIdr : PacketEncoder.frameTypeP,
    sequenceNumber: seq,
    ptsUs: seq * 33333,
    payload: payload,
  );
  return CameraPacket(cameraId, PacketDecoder.decode(wire));
}

class FakeDecoderBackend implements VideoDecoderBackend {
  final fed = <Uint8List>[];
  final released = <int>[];
  final sizes = StreamController<(int, int, int)>.broadcast();
  bool failCreate = false;

  @override
  Future<int> create() async {
    if (failCreate) throw StateError('no decoder');
    return 42;
  }

  @override
  Future<void> feed(int textureId, Uint8List data, int ptsUs) async => fed.add(data);

  @override
  Future<void> release(int textureId) async => released.add(textureId);

  @override
  Stream<(int, int, int)> get videoSizes => sizes.stream;
}

void main() {
  group('H264Nal', () {
    test('finds NAL types after 3- and 4-byte start codes', () {
      expect(H264Nal.types(bytes([_sps, _pps, _idr])), [7, 8, 5]);
      expect(H264Nal.types(Uint8List.fromList([0, 0, 1, 0x41, 1, 2])), [1]);
    });

    test('decoder entry point needs SPS and an IDR slice', () {
      expect(H264Nal.isDecoderEntryPoint(bytes([_sps, _pps, _idr])), isTrue);
      expect(H264Nal.isDecoderEntryPoint(bytes([_idr])), isFalse);
      expect(H264Nal.isDecoderEntryPoint(bytes([_sps, _pps])), isFalse);
      expect(H264Nal.isDecoderEntryPoint(bytes([_p])), isFalse);
    });
  });

  group('LiveVideoController', () {
    late StreamController<CameraPacket> packets;
    late FakeDecoderBackend backend;
    late List<String> keyframeRequests;

    setUp(() {
      packets = StreamController<CameraPacket>.broadcast();
      backend = FakeDecoderBackend();
      keyframeRequests = [];
    });

    LiveVideoController controller() => LiveVideoController(
          cameraId: 'cam_a',
          packets: packets.stream,
          requestKeyframe: (id) {
            keyframeRequests.add(id);
            return true;
          },
          backend: backend,
        );

    test('asks for a keyframe and skips packets until one it can decode', () async {
      final c = controller();
      await c.start();
      expect(keyframeRequests, ['cam_a']);
      expect(c.state, LiveVideoState.waitingForKeyframe);

      packets.add(cameraPacket('cam_a', bytes([_p]), seq: 1));
      packets.add(cameraPacket('cam_a', bytes([_idr]), seq: 2)); // IDR without SPS: not enough
      await pumpEventQueue();
      expect(backend.fed, isEmpty);
      expect(c.packetsSkipped, 2);

      packets.add(cameraPacket('cam_a', bytes([_sps, _pps, _idr]), seq: 3));
      packets.add(cameraPacket('cam_a', bytes([_p]), seq: 4));
      await pumpEventQueue();
      expect(c.state, LiveVideoState.playing);
      expect(backend.fed.length, 2);
      c.dispose();
    });

    test('ignores other cameras and tracks video size', () async {
      final c = controller();
      await c.start();
      packets.add(cameraPacket('cam_b', bytes([_sps, _pps, _idr])));
      backend.sizes.add((42, 1920, 1080));
      backend.sizes.add((7, 640, 480)); // a different texture
      await pumpEventQueue();
      expect(backend.fed, isEmpty);
      expect((c.videoWidth, c.videoHeight), (1920, 1080));
      c.dispose();
    });

    test('dispose stops forwarding and releases the texture', () async {
      final c = controller();
      await c.start();
      c.dispose();
      packets.add(cameraPacket('cam_a', bytes([_sps, _pps, _idr])));
      await pumpEventQueue();
      expect(backend.fed, isEmpty);
      expect(backend.released, [42]);
    });

    test('reports failure when no decoder is available', () async {
      backend.failCreate = true;
      final c = controller();
      await c.start();
      expect(c.state, LiveVideoState.failed);
      expect(c.error, contains('decoder'));
      c.dispose();
    });

    test('resync waits for the next keyframe again', () async {
      final c = controller();
      await c.start();
      packets.add(cameraPacket('cam_a', bytes([_sps, _pps, _idr])));
      await pumpEventQueue();
      c.resync();
      expect(c.state, LiveVideoState.waitingForKeyframe);
      expect(keyframeRequests.length, 2);
      c.dispose();
    });
  });

  group('control channel (loopback)', () {
    test('ControlClient.parseCommand accepts only device commands', () {
      expect(ControlClient.parseCommand('{"type":"device_control_command","action":"request_idr"}')?['action'], 'request_idr');
      expect(ControlClient.parseCommand('{"type":"pong"}'), isNull);
      expect(ControlClient.parseCommand('not json'), isNull);
      expect(ControlClient.parseCommand(42), isNull);
    });

    test('main phone keyframe request reaches the camera; telemetry carries rotation', () async {
      final registry = DeviceRegistry(store: InMemoryDeviceStore());
      await registry.load();
      final server = HubServer(registry: registry, port: 0, bindAddress: InternetAddress.loopbackIPv4);
      await server.start();
      final port = server.boundPort!;

      await PairingClient.requestPairing(hubIp: '127.0.0.1', hubPort: port, deviceId: 'dev_cam_1', deviceName: 'Camera');
      final paired = await PairingClient.verifyPairing(
          hubIp: '127.0.0.1', hubPort: port, deviceId: 'dev_cam_1', pin: registry.pendingPairings.single.pin);

      final commands = StreamController<Map<String, dynamic>>();
      final client = ControlClient(
        hubIp: '127.0.0.1',
        hubPort: port,
        deviceId: 'dev_cam_1',
        cameraId: paired.cameraId!,
        deviceToken: paired.deviceToken!,
        sensorOrientation: 90,
        fpsProvider: () => 29.5,
        onCommand: commands.add,
      );
      await client.start();
      expect(client.isConnected, isTrue);
      expect(server.cameras.single.controlConnected, isTrue);

      expect(server.requestKeyframe(paired.cameraId!), isTrue);
      final cmd = await commands.stream.firstWhere((c) => c['action'] == 'request_idr').timeout(const Duration(seconds: 2));
      expect(cmd['action'], 'request_idr');

      // Telemetry is sent once per second.
      for (var i = 0; i < 60 && server.cameras.single.cameraFps == null; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 50));
      }
      expect(server.cameras.single.rotationDegrees, 90);
      expect(server.cameras.single.cameraFps, 29.5);

      client.stop();
      await server.dispose();
    });
  });
}
