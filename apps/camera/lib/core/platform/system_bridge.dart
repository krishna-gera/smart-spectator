import 'package:flutter/services.dart';

/// Android system services used by both modes (MainActivity.kt "system" channel).
/// Every call is best-effort: failures never break streaming.
class SystemBridge {
  static const _channel = MethodChannel('com.smartspectator/system');

  /// Keeps the main phone's hub running with the screen off (foreground service).
  static Future<void> startHubService({String? text}) => _call('startHubService', {'text': text});

  static Future<void> stopHubService() => _call('stopHubService');

  /// Camera phones keep the screen on while streaming (Android stops camera
  /// access for background apps).
  static Future<void> keepScreenOn(bool enabled) => _call('keepScreenOn', {'enabled': enabled});

  /// Asks for permission to show alerts (Android 13+, iOS).
  static Future<void> requestNotificationPermission() => _call('requestNotificationPermission');

  /// Shows a local notification (best-effort; silently skipped if not allowed).
  static Future<void> notify({required int id, required String title, required String body}) =>
      _call('notify', {'id': id, 'title': title, 'body': body});

  static const hubServiceType = '_smartspectator._tcp';
  static const cameraServiceType = '_ss-camera._tcp';

  /// Advertises the main phone's hub on the LAN as _smartspectator._tcp.
  static Future<void> advertiseHub(int port, String name) => advertise(hubServiceType, port, name);

  /// Advertises a camera phone (for "add camera by its code") as _ss-camera._tcp.
  static Future<void> advertiseCamera(int port, String name) => advertise(cameraServiceType, port, name);

  static Future<void> advertise(String type, int port, String name) =>
      _call('nsdRegister', {'port': port, 'name': name, 'type': type});

  static Future<void> stopAdvertisingHub() => _call('nsdUnregister');

  /// Browses the LAN for main phones. Returns (host, port, name) records.
  static Future<List<(String, int, String)>> discoverHubs({Duration timeout = const Duration(seconds: 3)}) =>
      discover(hubServiceType, timeout: timeout);

  static Future<List<(String, int, String)>> discover(String type, {Duration timeout = const Duration(seconds: 3)}) async {
    try {
      final raw = await _channel.invokeMethod<List<dynamic>>('nsdDiscover', {'timeoutMs': timeout.inMilliseconds, 'type': type});
      return (raw ?? []).map((e) {
        final m = Map<String, dynamic>.from(e as Map);
        return (m['host'] as String, (m['port'] as num).toInt(), m['name'] as String? ?? 'Main phone');
      }).toList();
    } catch (_) {
      return [];
    }
  }

  static Future<void> _call(String method, [Map<String, Object?>? args]) async {
    try {
      await _channel.invokeMethod(method, args);
    } catch (_) {}
  }
}
