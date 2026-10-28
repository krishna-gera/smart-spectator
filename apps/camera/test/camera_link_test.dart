import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/camera/camera_link_server.dart';
import 'package:smart_spectator_camera/core/pairing/code_guard.dart';
import 'package:smart_spectator_camera/core/pairing/pairing_client.dart';
import 'package:smart_spectator_camera/core/storage/credential_store.dart';
import 'package:smart_spectator_camera/hub/camera_adder.dart';
import 'package:smart_spectator_camera/hub/device_registry.dart';

/// Main phone adds a camera by the camera's code (camera → several main phones).
void main() {
  late CodeGuard guard;
  late CameraLinkServer camera;
  late List<HubLink> links;
  late DiscoveredCamera discovered;

  setUp(() async {
    guard = CodeGuard(code: '482913', maxFailures: 3);
    links = [];
    camera = CameraLinkServer(
      deviceId: 'dev_cam_kitchen',
      deviceName: 'Camera K1',
      guard: guard,
      bindAddress: InternetAddress.loopbackIPv4,
      onLinked: (l) async => links.add(l),
    );
    final port = await camera.start(preferredPort: 0);
    discovered = (await CameraAdder.probe(HubAddress('127.0.0.1', port)))!;
  });

  tearDown(() async => camera.stop());

  Future<DeviceRegistry> mainPhone() async {
    final r = DeviceRegistry(store: InMemoryDeviceStore());
    await r.load();
    return r;
  }

  test('probe identifies the camera phone', () {
    expect(discovered.deviceId, 'dev_cam_kitchen');
    expect(discovered.name, 'Camera K1');
  });

  test('the same camera code adds the camera to two main phones', () async {
    final phoneA = await mainPhone();
    final phoneB = await mainPhone();
    expect(await CameraAdder.add(camera: discovered, code: '482913', registry: phoneA, hubPort: 8000, hubName: 'Main A'), isNull);
    expect(await CameraAdder.add(camera: discovered, code: '482913', registry: phoneB, hubPort: 8001, hubName: 'Main B'), isNull);

    expect(links.map((l) => (l.hubName, l.hubPort)), [('Main A', 8000), ('Main B', 8001)]);
    // The address is taken from the connection, not from what the caller claims.
    expect(links.every((l) => l.hubHost == '127.0.0.1'), isTrue);
    // Each main phone accepts the token it issued for this camera.
    expect(phoneA.authenticate(links[0].deviceToken)?.deviceId, 'dev_cam_kitchen');
    expect(phoneB.authenticate(links[1].deviceToken)?.deviceId, 'dev_cam_kitchen');
    expect(phoneA.authenticate(links[1].deviceToken), isNull);
  });

  test('a wrong code changes nothing on either phone', () async {
    final phone = await mainPhone();
    final error = await CameraAdder.add(camera: discovered, code: '000000', registry: phone, hubPort: 8000, hubName: 'Main');
    expect(error, contains('not correct'));
    expect(links, isEmpty);
    expect(phone.devices, isEmpty, reason: 'no credential issued before the code is confirmed');
  });

  test('guessing is locked out after repeated wrong codes', () async {
    final phone = await mainPhone();
    for (var i = 0; i < 3; i++) {
      await CameraAdder.add(camera: discovered, code: '000000', registry: phone, hubPort: 8000, hubName: 'Main');
    }
    final error = await CameraAdder.add(camera: discovered, code: '482913', registry: phone, hubPort: 8000, hubName: 'Main');
    expect(error, contains('Try again'));
    expect(links, isEmpty);
  });

  test('unreachable camera gives a readable error', () async {
    final phone = await mainPhone();
    final gone = DiscoveredCamera(address: const HubAddress('127.0.0.1', 1), deviceId: 'x', name: 'x');
    expect(await CameraAdder.add(camera: gone, code: '482913', registry: phone, hubPort: 8000, hubName: 'Main'),
        contains('Could not reach the camera'));
  });

  test('code guard: permanent until changed, lockout expires', () {
    var now = DateTime(2026, 10, 28);
    final g = CodeGuard(code: '123456', maxFailures: 2, lockout: const Duration(minutes: 5), now: () => now);
    expect(g.check('123456').ok, isTrue);
    g.check('000000');
    expect(g.check('000000').locked, isTrue);
    expect(g.check('123456').ok, isFalse);
    now = now.add(const Duration(minutes: 6));
    expect(g.check('123456').ok, isTrue);
    final fresh = g.regenerate();
    expect(fresh, isNot('123456'));
    expect(CodeGuard(code: 'bad').code, matches(RegExp(r'^\d{6}$')));
  });
}
