import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/core/control/control_client.dart';
import 'package:smart_spectator_camera/core/motion/motion_reporter.dart';
import 'package:smart_spectator_camera/core/pairing/pairing_client.dart';
import 'package:smart_spectator_camera/hub/camera_health.dart';
import 'package:smart_spectator_camera/hub/device_registry.dart';
import 'package:smart_spectator_camera/hub/hub_server.dart';

final _jpeg = Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 3, 3, 3, 0xFF, 0xD9]);

void main() {
  group('CameraLink.health', () {
    final now = DateTime(2026, 10, 28, 12);
    CameraLink link() => CameraLink(cameraId: 'c', deviceId: 'd', deviceName: 'Hall');

    test('online, reconnecting within a minute, then offline', () {
      final c = link()..controlConnected = true;
      expect(c.health(now), CameraHealth.online);
      c
        ..controlConnected = false
        ..disconnectedAt = now.subtract(const Duration(seconds: 20));
      expect(c.health(now), CameraHealth.reconnecting);
      expect(c.health(now.add(const Duration(seconds: 41))), CameraHealth.offline);
    });

    test('streaming without recent packets is still connecting', () {
      final c = link()
        ..controlConnected = true
        ..streaming = true;
      expect(c.health(now), CameraHealth.connecting);
    });

    test('low battery only when not charging', () {
      final c = link()..batteryLevel = 12;
      expect(c.batteryLow, isTrue);
      c.isCharging = true;
      expect(c.batteryLow, isFalse);
    });
  });

  group('CameraHealthMonitor', () {
    late DateTime now;
    late List<String> titles;
    late CameraHealthMonitor monitor;

    setUp(() {
      now = DateTime(2026, 10, 28, 12);
      titles = [];
      monitor = CameraHealthMonitor(
        notify: ({required id, required title, required body}) async => titles.add(title),
        now: () => now,
      );
    });

    test('low battery warns once and re-arms after charging', () async {
      final c = CameraLink(cameraId: 'c', deviceId: 'd', deviceName: 'Garage')
        ..controlConnected = true
        ..batteryLevel = 14;
      await monitor.check([c]);
      await monitor.check([c]);
      expect(titles, ['🔋 Garage: battery low']);
      c.isCharging = true;
      await monitor.check([c]);
      c
        ..isCharging = false
        ..batteryLevel = 10;
      await monitor.check([c]);
      expect(titles.length, 2);
    });

    test('offline warning only for a camera that dropped while streaming, after a minute', () async {
      final streaming = CameraLink(cameraId: 'a', deviceId: 'a', deviceName: 'Door')
        ..disconnectedAt = now
        ..droppedWhileStreaming = true;
      final idle = CameraLink(cameraId: 'b', deviceId: 'b', deviceName: 'Spare')
        ..disconnectedAt = now
        ..droppedWhileStreaming = false;
      await monitor.check([streaming, idle]);
      expect(titles, isEmpty, reason: 'still within the reconnect grace period');
      now = now.add(const Duration(seconds: 61));
      await monitor.check([streaming, idle]);
      await monitor.check([streaming, idle]);
      expect(titles, ['📴 Door went offline']);
    });

    test('switched off: no warnings', () async {
      monitor.enabled = false;
      await monitor.check([
        CameraLink(cameraId: 'c', deviceId: 'd', deviceName: 'X')
          ..controlConnected = true
          ..batteryLevel = 5,
      ]);
      expect(titles, isEmpty);
    });
  });

  test('describeAgo', () {
    final now = DateTime(2026, 10, 28, 12);
    expect(describeAgo(null, now), 'not yet');
    expect(describeAgo(now.subtract(const Duration(seconds: 3)), now), 'just now');
    expect(describeAgo(now.subtract(const Duration(minutes: 5)), now), '5 min ago');
    expect(describeAgo(now.subtract(const Duration(hours: 3)), now), '3 h ago');
  });

  group('hub', () {
    late DeviceRegistry registry;
    late HubServer server;
    late HubAddress hub;

    setUp(() async {
      registry = DeviceRegistry(store: InMemoryDeviceStore());
      await registry.load();
      server = HubServer(registry: registry, port: 0, bindAddress: InternetAddress.loopbackIPv4);
      await server.start();
      hub = HubAddress('127.0.0.1', server.boundPort!);
    });

    tearDown(() => server.dispose());

    test('telemetry marks the camera seen; dropping records the time; snapshots keep a last picture', () async {
      final cam = await PairingClient.pairWithCode(hub: hub, deviceId: 'dev_a', deviceName: 'Laundry', code: registry.hubCode);
      final reporter = MotionReporter(hub: hub, deviceToken: cam.deviceToken!);
      final control = ControlClient(
        hubIp: '127.0.0.1',
        hubPort: hub.port,
        deviceId: 'dev_a',
        cameraId: cam.cameraId!,
        deviceToken: cam.deviceToken!,
        onCommand: (cmd) {
          if (cmd['action'] == 'capture_snapshot') reporter.uploadSnapshot(requestId: cmd['request_id'] as String, jpeg: _jpeg);
        },
      );
      await control.start();
      final link = server.cameras.single;
      for (var i = 0; i < 50 && !link.controlConnected; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 20));
      }
      expect(link.health(), CameraHealth.online);
      expect(link.lastSeenAt, isNotNull);

      expect(await server.requestSnapshot(cam.cameraId!), _jpeg);
      expect(link.lastPicture, _jpeg);
      expect(link.lastPictureAt, isNotNull);

      control.stop();
      for (var i = 0; i < 50 && link.controlConnected; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 20));
      }
      expect(link.health(), CameraHealth.reconnecting);
      expect(link.droppedWhileStreaming, isFalse);
    });

    test('rename is saved on the main phone and validated', () async {
      final cam = await PairingClient.pairWithCode(hub: hub, deviceId: 'dev_a', deviceName: 'iPhone', code: registry.hubCode);
      expect(await server.renameCamera(cam.cameraId!, '  Front door  '), isTrue);
      expect(server.cameras.single.deviceName, 'Front door');
      expect(registry.devices.single.deviceName, 'Front door');
      expect(await server.renameCamera(cam.cameraId!, '   '), isFalse);
      expect(await server.renameCamera('cam_nope', 'X'), isFalse);
    });
  });
}
