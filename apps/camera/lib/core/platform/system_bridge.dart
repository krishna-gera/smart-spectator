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

  /// Advertises the main phone's hub on the LAN as _smartspectator._tcp.
  static Future<void> advertiseHub(int port, String name) => _call('nsdRegister', {'port': port, 'name': name});

  static Future<void> stopAdvertisingHub() => _call('nsdUnregister');

  /// Browses the LAN for main phones. Returns (host, port, name) records.
  static Future<List<(String, int, String)>> discoverHubs({Duration timeout = const Duration(seconds: 3)}) async {
    try {
      final raw = await _channel.invokeMethod<List<dynamic>>('nsdDiscover', {'timeoutMs': timeout.inMilliseconds});
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
