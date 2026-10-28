import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/core/discovery/hub_discovery.dart';
import 'package:smart_spectator_camera/core/pairing/pairing_client.dart';
import 'package:smart_spectator_camera/hub/device_registry.dart';
import 'package:smart_spectator_camera/hub/hub_server.dart';

void main() {
  group('HubAddress.tryParse', () {
    test('accepts host and host:port (the input that used to hang pairing)', () {
      expect(HubAddress.tryParse('10.6.10.94'), const HubAddress('10.6.10.94', 8000));
      expect(HubAddress.tryParse(' 10.6.10.94:8000 '), const HubAddress('10.6.10.94', 8000));
      expect(HubAddress.tryParse('10.6.10.94:8001'), const HubAddress('10.6.10.94', 8001));
      expect(HubAddress.tryParse('http://10.6.10.94:8000/'), const HubAddress('10.6.10.94', 8000));
      expect(HubAddress.tryParse('10.6.10.94:8000').toString(), '10.6.10.94');
    });

    test('rejects malformed input', () {
      expect(HubAddress.tryParse(''), isNull);
      expect(HubAddress.tryParse('10.6.10.94:8000:8000'), isNull);
      expect(HubAddress.tryParse('10.6.10.94:abc'), isNull);
      expect(HubAddress.tryParse('10.6.10.94:70000'), isNull);
      expect(HubAddress.tryParse('bad host!'), isNull);
    });
  });

  group('registry hub code (permanent)', () {
    late DateTime now;
    late InMemoryDeviceStore store;
    late DeviceRegistry registry;

    setUp(() async {
      now = DateTime(2026, 10, 28, 12);
      store = InMemoryDeviceStore();
      registry = DeviceRegistry(store: store, now: () => now, maxHubCodeFailures: 3);
      await registry.load();
    });

    test('the code shown on the main phone pairs any camera in one step', () async {
      final code = registry.hubCode;
      expect(code, matches(RegExp(r'^\d{6}$')));
      final a = await registry.pairWithHubCode('dev_a', 'Camera A', code) as VerifySuccess;
      final b = await registry.pairWithHubCode('dev_b', 'Camera B', code) as VerifySuccess;
      expect(registry.authenticate(a.rawToken)?.deviceId, 'dev_a');
      expect(registry.authenticate(b.rawToken)?.deviceId, 'dev_b');
      expect(a.device.cameraId, isNot(b.device.cameraId));
    });

    test('the code never expires and survives an app restart', () async {
      final code = registry.hubCode;
      now = now.add(const Duration(days: 30));
      expect(registry.hubCode, code);
      final reloaded = DeviceRegistry(store: store, now: () => now);
      await reloaded.load();
      expect(reloaded.hubCode, code);
    });

    test('repeated wrong guesses pause pairing instead of changing the code', () async {
      final code = registry.hubCode;
      final wrong = code == '111111' ? '222222' : '111111';
      await registry.pairWithHubCode('dev_x', 'X', wrong);
      await registry.pairWithHubCode('dev_x', 'X', wrong);
      final third = await registry.pairWithHubCode('dev_x', 'X', wrong) as VerifyFailure;
      expect(third.message, contains('paused'));
      expect(registry.hubCode, code, reason: 'the code stays the same');
      // Even the right code is refused while paused.
      expect(await registry.pairWithHubCode('dev_x', 'X', code), isA<VerifyFailure>());
      now = now.add(const Duration(minutes: 6));
      expect(await registry.pairWithHubCode('dev_x', 'X', code), isA<VerifySuccess>());
    });

    test('change code replaces it, keeps paired cameras, and persists', () async {
      final old = registry.hubCode;
      final paired = await registry.pairWithHubCode('dev_a', 'A', old) as VerifySuccess;
      final fresh = await registry.changeHubCode();
      expect(fresh, isNot(old));
      expect(registry.authenticate(paired.rawToken), isNotNull);
      expect(await registry.pairWithHubCode('dev_b', 'B', old), isA<VerifyFailure>());
      final reloaded = DeviceRegistry(store: store, now: () => now);
      await reloaded.load();
      expect(reloaded.hubCode, fresh);
    });
  });

  group('code pairing over the network (loopback)', () {
    late DeviceRegistry registry;
    late HubServer server;
    late HubAddress hub;

    setUp(() async {
      registry = DeviceRegistry(store: InMemoryDeviceStore());
      await registry.load();
      server = HubServer(registry: registry, port: 0, bindAddress: InternetAddress.loopbackIPv4, displayName: 'Main phone (test)');
      await server.start();
      hub = HubAddress('127.0.0.1', server.boundPort!);
    });

    tearDown(() async => server.dispose());

    test('camera pairs with just the code', () async {
      final res = await PairingClient.pairWithCode(hub: hub, deviceId: 'dev_cam_1', deviceName: 'Camera 1', code: registry.hubCode);
      expect(res.success, isTrue, reason: res.errorMessage);
      expect(res.deviceToken, startsWith('ss_tok_v1_'));
      expect(server.cameras.single.deviceName, 'Camera 1');
    });

    test('wrong code gives a readable message', () async {
      final wrong = registry.hubCode == '123456' ? '654321' : '123456';
      final res = await PairingClient.pairWithCode(hub: hub, deviceId: 'dev_cam_1', deviceName: 'Camera 1', code: wrong);
      expect(res.success, isFalse);
      expect(res.errorMessage, contains('not correct'));
    });

    test('unreachable main phone fails quickly with a message instead of hanging', () async {
      final res = await PairingClient.pairWithCode(
          hub: const HubAddress('127.0.0.1', 1), deviceId: 'dev_cam_1', deviceName: 'Camera 1', code: '123456');
      expect(res.success, isFalse);
      expect(res.errorMessage, contains('Could not reach the main phone'));
    });

    test('discovery probe recognises a main phone and reads its name', () async {
      final found = await HubDiscovery.probeHub(hub);
      expect(found?.name, 'Main phone (test)');

      // Something else answering on a port is not mistaken for a main phone.
      final other = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      other.listen((r) {
        r.response.write(jsonEncode({'status': 'ok'}));
        r.response.close();
      });
      expect(await HubDiscovery.probeHub(HubAddress('127.0.0.1', other.port)), isNull);
      await other.close(force: true);
    });
  });
}
