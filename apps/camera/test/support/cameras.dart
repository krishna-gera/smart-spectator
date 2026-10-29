import 'package:smart_spectator_camera/hub/device_registry.dart';

/// A camera as the main phone sees it after it was added.
class TestCamera {
  final String deviceId;
  final String cameraId;
  final String deviceToken;
  const TestCamera(this.deviceId, this.cameraId, this.deviceToken);
}

/// Adds a camera to [registry] the way the app does after the user types the
/// camera's code (CameraAdder → DeviceRegistry.issueCredential).
Future<TestCamera> addCamera(DeviceRegistry registry, String deviceId, String deviceName) async {
  final (device, token) = await registry.issueCredential(deviceId, deviceName);
  return TestCamera(device.deviceId, device.cameraId, token);
}
