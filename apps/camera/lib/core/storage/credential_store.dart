import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

class DeviceCredentials {
  final String deviceId;
  final String? deviceToken;
  final String? cameraId;
  final String? hubIp;
  final int hubPort;

  DeviceCredentials({
    required this.deviceId,
    this.deviceToken,
    this.cameraId,
    this.hubIp,
    this.hubPort = 8000,
  });

  bool get isPaired => deviceToken != null && deviceToken!.isNotEmpty;
}

class CredentialStore {
  static const _keyDeviceId = 'ss_device_id';
  static const _keyDeviceToken = 'ss_device_token';
  static const _keyCameraId = 'ss_camera_id';
  static const _keyHubIp = 'ss_last_hub_ip';
  static const _keyHubPort = 'ss_last_hub_port';

  static Future<DeviceCredentials> load() async {
    final prefs = await SharedPreferences.getInstance();
    String? deviceId = prefs.getString(_keyDeviceId);
    if (deviceId == null) {
      deviceId = 'dev_android_${const Uuid().v4().substring(0, 10)}';
      await prefs.setString(_keyDeviceId, deviceId);
    }

    final token = prefs.getString(_keyDeviceToken);
    final cameraId = prefs.getString(_keyCameraId);
    final hubIp = prefs.getString(_keyHubIp);
    final hubPort = prefs.getInt(_keyHubPort) ?? 8000;

    return DeviceCredentials(
      deviceId: deviceId,
      deviceToken: token,
      cameraId: cameraId,
      hubIp: hubIp,
      hubPort: hubPort,
    );
  }

  static Future<void> save({
    required String deviceToken,
    required String cameraId,
    required String hubIp,
    int hubPort = 8000,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyDeviceToken, deviceToken);
    await prefs.setString(_keyCameraId, cameraId);
    await prefs.setString(_keyHubIp, hubIp);
    await prefs.setInt(_keyHubPort, hubPort);
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyDeviceToken);
    await prefs.remove(_keyCameraId);
  }
}
