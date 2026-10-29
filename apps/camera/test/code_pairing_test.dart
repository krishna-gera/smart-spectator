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

  group('web dashboard code (permanent)', () {
    late DateTime now;
    late InMemoryDeviceStore store;
    late DeviceRegistry registry;

    setUp(() async {
      now = DateTime(2026, 10, 28, 12);
      store = InMemoryDeviceStore();
      registry = DeviceRegistry(store: store, now: () => now, maxHubCodeFailures: 3);
      await registry.load();
    });

    test('the code is 6 digits, never expires and survives an app restart', () async {
      final code = registry.hubCode;
      expect(code, matches(RegExp(r'^\d{6}$')));
      expect(registry.checkHubCode(code).ok, isTrue);
      now = now.add(const Duration(days: 30));
      expect(registry.hubCode, code);
      final reloaded = DeviceRegistry(store: store, now: () => now);
      await reloaded.load();
      expect(reloaded.hubCode, code);
    });

    test('repeated wrong guesses pause sign-in instead of changing the code', () async {
      final code = registry.hubCode;
      final wrong = code == '111111' ? '222222' : '111111';
      registry.checkHubCode(wrong);
      registry.checkHubCode(wrong);
      expect(registry.checkHubCode(wrong).locked, isTrue);
      expect(registry.hubCode, code, reason: 'the code stays the same');
      expect(registry.checkHubCode(code).ok, isFalse, reason: 'even the right code waits out the pause');
      now = now.add(const Duration(minutes: 6));
      expect(registry.checkHubCode(code).ok, isTrue);
    });

    test('change code replaces it, keeps cameras, and persists', () async {
      final old = registry.hubCode;
      final (_, token) = await registry.issueCredential('dev_a', 'A');
      final fresh = await registry.changeHubCode();
      expect(fresh, isNot(old));
      expect(registry.authenticate(token), isNotNull);
      expect(registry.checkHubCode(old).ok, isFalse);
      final reloaded = DeviceRegistry(store: store, now: () => now);
      await reloaded.load();
      expect(reloaded.hubCode, fresh);
    });
  });

  group('finding a main phone (loopback)', () {
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
