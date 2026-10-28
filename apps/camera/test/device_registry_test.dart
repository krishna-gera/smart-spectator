import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/hub/device_registry.dart';

void main() {
  late DateTime now;
  late InMemoryDeviceStore store;
  late DeviceRegistry registry;

  setUp(() async {
    now = DateTime(2026, 10, 28, 12);
    store = InMemoryDeviceStore();
    registry = DeviceRegistry(store: store, now: () => now);
    await registry.load();
  });

  Future<VerifySuccess> pair(String deviceId) async {
    final pin = registry.requestPairing(deviceId, 'Camera')!.pin;
    return await registry.verifyPairing(deviceId, pin) as VerifySuccess;
  }

  test('a repeated request keeps the same PIN while it is valid', () {
    final first = registry.requestPairing('dev_a', 'Camera A')!;
    final second = registry.requestPairing('dev_a', 'Camera A')!;
    expect(second.pin, first.pin);
    expect(first.pin, matches(RegExp(r'^\d{6}$')));
  });

  test('an expired PIN is replaced and cannot be verified', () async {
    final first = registry.requestPairing('dev_a', 'Camera A')!;
    now = now.add(const Duration(minutes: 6));
    expect(await registry.verifyPairing('dev_a', first.pin), isA<VerifyFailure>());
    final second = registry.requestPairing('dev_a', 'Camera A')!;
    expect(second.expiresAt.isAfter(now), isTrue);
  });

  test('correct PIN issues a token that authenticates', () async {
    final ok = await pair('dev_a');
    expect(ok.rawToken, startsWith(DeviceRegistry.tokenPrefix));
    expect(registry.authenticate(ok.rawToken)?.deviceId, 'dev_a');
    expect(registry.pendingPairings, isEmpty);
  });

  test('three wrong PINs cancel the request', () async {
    final req = registry.requestPairing('dev_a', 'Camera A')!;
    final wrong = req.pin == '111111' ? '222222' : '111111';
    expect((await registry.verifyPairing('dev_a', wrong) as VerifyFailure).message, contains('2 attempt'));
    await registry.verifyPairing('dev_a', wrong);
    expect((await registry.verifyPairing('dev_a', wrong) as VerifyFailure).message, contains('Request a new code'));
    expect(await registry.verifyPairing('dev_a', req.pin), isA<VerifyFailure>());
  });

  test('unknown, malformed and revoked tokens are rejected', () async {
    final ok = await pair('dev_a');
    expect(registry.authenticate(null), isNull);
    expect(registry.authenticate('not_a_token'), isNull);
    expect(registry.authenticate('${DeviceRegistry.tokenPrefix}deadbeef'), isNull);
    await registry.revoke('dev_a');
    expect(registry.authenticate(ok.rawToken), isNull);
  });

  test('re-pairing keeps the camera id and invalidates the old token', () async {
    final first = await pair('dev_a');
    final second = await pair('dev_a');
    expect(second.device.cameraId, first.device.cameraId);
    expect(registry.authenticate(first.rawToken), isNull);
    expect(registry.authenticate(second.rawToken), isNotNull);
  });

  test('paired devices and the token secret survive a restart', () async {
    final ok = await pair('dev_a');
    final reloaded = DeviceRegistry(store: store, now: () => now);
    await reloaded.load();
    expect(reloaded.authenticate(ok.rawToken)?.cameraId, ok.device.cameraId);
  });

  test('limits how many pairing requests can be pending', () {
    final limited = DeviceRegistry(store: store, maxPendingRequests: 2, now: () => now);
    expect(limited.requestPairing('dev_1', 'a'), isNotNull);
    expect(limited.requestPairing('dev_2', 'b'), isNotNull);
    expect(limited.requestPairing('dev_3', 'c'), isNull);
    // An existing request is still returned.
    expect(limited.requestPairing('dev_1', 'a'), isNotNull);
  });

  test('device id validation', () {
    expect(DeviceRegistry.isValidDeviceId('dev_android_1a2b3c'), isTrue);
    expect(DeviceRegistry.isValidDeviceId('ab'), isFalse);
    expect(DeviceRegistry.isValidDeviceId('bad id!'), isFalse);
  });
}
