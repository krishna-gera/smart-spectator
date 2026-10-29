import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
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
  // What the camera's owner answers on the camera phone (null: no answer).
  late Future<bool> Function(LinkRequest) owner;
  late List<LinkRequest> asked;

  setUp(() async {
    guard = CodeGuard(code: '482913', maxFailures: 3);
    links = [];
    asked = [];
    owner = (_) async => true;
    camera = CameraLinkServer(
      deviceId: 'dev_cam_kitchen',
      deviceName: 'Camera K1',
      guard: guard,
      bindAddress: InternetAddress.loopbackIPv4,
      approvalTimeout: const Duration(milliseconds: 300),
      approve: (r) {
        asked.add(r);
        return owner(r);
      },
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
    expect(asked.map((r) => (r.hubName, r.hubHost)), [('Main A', '127.0.0.1'), ('Main B', '127.0.0.1')],
        reason: 'the owner allowed each main phone on the camera');
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

  test('one-step add by code: the main phone finds the right camera among several', () async {
    final otherLinks = <HubLink>[];
    final other = CameraLinkServer(
      deviceId: 'dev_cam_garage',
      deviceName: 'Camera G1',
      guard: CodeGuard(code: '111222'),
      bindAddress: InternetAddress.loopbackIPv4,
      approve: (_) async => true,
      onLinked: (l) async => otherLinks.add(l),
    );
    final otherCam = (await CameraAdder.probe(HubAddress('127.0.0.1', await other.start(preferredPort: 0))))!;
    final phone = await mainPhone();
    final statuses = <String>[];

    final name = await CameraAdder.addByCode(
      code: '482913',
      registry: phone,
      hubPort: 8000,
      hubName: 'Main',
      onStatus: statuses.add,
      discovery: () => Stream.fromIterable([otherCam, discovered]),
    );
    expect(name, 'Camera K1');
    expect(links.single.hubName, 'Main');
    expect(otherLinks, isEmpty);
    expect(phone.devices.single.deviceId, 'dev_cam_kitchen');
    expect(statuses.first, contains('Looking'));
    expect(statuses, contains(contains('Tap Allow on Camera K1')));
    await other.stop();
  });

  test('one-step add by code: clear errors when nothing is found or the code is wrong', () async {
    final phone = await mainPhone();
    expect(
      () => CameraAdder.addByCode(code: '482913', registry: phone, hubPort: 8000, hubName: 'Main', discovery: () => const Stream.empty()),
      throwsA(isA<AddCameraError>().having((e) => e.message, 'message', contains('No camera found'))),
    );
    await expectLater(
      CameraAdder.addByCode(code: '000000', registry: phone, hubPort: 8000, hubName: 'Main', discovery: () => Stream.value(discovered)),
      throwsA(isA<AddCameraError>()),
    );
    expect(links, isEmpty);
    expect(phone.devices, isEmpty);
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

  group('the camera owner allows each new main phone', () {
    Future<http.Response> post(String path, Map<String, dynamic> body, {Map<String, String> headers = const {}}) =>
        http.post(discovered.address.uri(path), headers: {'Content-Type': 'application/json', ...headers}, body: jsonEncode(body));

    test('"Don\'t allow" refuses the main phone and leaves nothing behind', () async {
      owner = (_) async => false;
      final phone = await mainPhone();
      final error = await CameraAdder.add(camera: discovered, code: '482913', registry: phone, hubPort: 8000, hubName: 'Stranger');
      expect(error, contains('did not allow'));
      expect(asked.single.hubName, 'Stranger');
      expect(links, isEmpty);
      expect(phone.devices, isEmpty, reason: 'no credential is issued unless the camera allows it');

      // Asking again straight away is refused without bothering the owner.
      final again = await CameraAdder.add(camera: discovered, code: '482913', registry: phone, hubPort: 8000, hubName: 'Stranger');
      expect(again, contains('Try again in a moment'));
      expect(asked, hasLength(1));
    });

    test('no answer on the camera: refused, and the question closes itself', () async {
      final never = Completer<bool>();
      owner = (_) => never.future;
      final phone = await mainPhone();
      final error = await CameraAdder.add(camera: discovered, code: '482913', registry: phone, hubPort: 8000, hubName: 'Main');
      expect(error, contains('Nobody answered'));
      await asked.single.closed.timeout(const Duration(seconds: 1));
      expect(links, isEmpty);
      expect(phone.devices, isEmpty);
    });

    test('the code alone is not enough: linking needs a fresh, single-use approval', () async {
      final link = {'code': '482913', 'hub_port': 8000, 'hub_name': 'Old main phone', 'camera_id': 'cam_x1', 'device_token': 'ss_tok_v1_abc'};
      final noApproval = await post('/api/v1/camera/link', link);
      expect(noApproval.statusCode, 403);
      expect(jsonDecode(noApproval.body)['detail'], contains('update VYRO on the main phone'));
      expect(await post('/api/v1/camera/link', {...link, 'approval': 'made-up'}).then((r) => r.statusCode), 403);

      final approval = jsonDecode((await post('/api/v1/camera/link/approve', {'code': '482913', 'hub_name': 'Main'})).body)['approval'];
      expect((await post('/api/v1/camera/link', {...link, 'approval': approval})).statusCode, 200);
      expect((await post('/api/v1/camera/link', {...link, 'approval': approval})).statusCode, 403, reason: 'single use');
      expect(links, hasLength(1));
    });

    test('a wrong code never reaches the owner, and one question is asked at a time', () async {
      expect((await post('/api/v1/camera/link/approve', {'code': '000000', 'hub_name': 'Main'})).statusCode, 400);
      expect(asked, isEmpty);

      final answer = Completer<bool>();
      owner = (_) => answer.future;
      final first = post('/api/v1/camera/link/approve', {'code': '482913', 'hub_name': 'A'});
      while (asked.isEmpty) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
      final second = await post('/api/v1/camera/link/approve', {'code': '482913', 'hub_name': 'B'});
      expect(second.statusCode, 409);
      answer.complete(true);
      expect((await first).statusCode, 200);
      expect(asked.map((r) => r.hubName), ['A']);
    });

    test('requests that reach the camera through another domain name are refused', () async {
      final res = await http.get(discovered.address.uri('/api/v1/camera/info'), headers: {'Host': 'rebind.example.com'});
      expect(res.statusCode, 421);
      for (final host in ['127.0.0.1:8100', 'camera-k1.local', 'localhost:8100', '[::1]:8100']) {
        expect((await http.get(discovered.address.uri('/api/v1/camera/info'), headers: {'Host': host})).statusCode, 200, reason: host);
      }
    });
  });
}
