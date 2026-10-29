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

  // Cameras are added by their own code; CameraAdder then calls this.
  Future<(PairedDevice, String)> pair(String deviceId) => registry.issueCredential(deviceId, 'Camera');

  test('an issued token authenticates its camera', () async {
    final (device, token) = await pair('dev_a');
    expect(token, startsWith(DeviceRegistry.tokenPrefix));
    expect(registry.authenticate(token)?.deviceId, 'dev_a');
    expect(device.cameraId, startsWith('cam_'));
  });

  test('unknown, malformed and revoked tokens are rejected', () async {
    final (_, token) = await pair('dev_a');
    expect(registry.authenticate(null), isNull);
    expect(registry.authenticate('not_a_token'), isNull);
    expect(registry.authenticate('${DeviceRegistry.tokenPrefix}deadbeef'), isNull);
    await registry.revoke('dev_a');
    expect(registry.authenticate(token), isNull);
    expect(registry.isRemovedToken(token), isTrue);
  });

  test('re-adding keeps the camera id and invalidates the old token', () async {
    final (first, firstToken) = await pair('dev_a');
    final (second, secondToken) = await pair('dev_a');
    expect(second.cameraId, first.cameraId);
    expect(registry.authenticate(firstToken), isNull);
    expect(registry.authenticate(secondToken), isNotNull);
  });

  test('paired devices and the token secret survive a restart', () async {
    final (device, token) = await pair('dev_a');
    final reloaded = DeviceRegistry(store: store, now: () => now);
    await reloaded.load();
    expect(reloaded.authenticate(token)?.cameraId, device.cameraId);
  });

  test('device id validation', () {
    expect(DeviceRegistry.isValidDeviceId('dev_android_1a2b3c'), isTrue);
    expect(DeviceRegistry.isValidDeviceId('ab'), isFalse);
    expect(DeviceRegistry.isValidDeviceId('bad id!'), isFalse);
  });
}
