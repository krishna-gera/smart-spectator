import 'hub_server.dart';
import 'alert_service.dart' show Notifier;

/// Warns on the main phone when a camera's battery runs low or a camera that
/// was streaming drops off the network. Each warning fires once and re-arms
/// when the camera recovers (charging / back above [recoverPercent], or
/// reconnected).
class CameraHealthMonitor {
  static const lowPercent = 15;
  static const recoverPercent = 25;

  final Notifier notify;
  final DateTime Function() _now;

  /// Switched from Settings ("Camera health alerts").
  bool enabled;

  final Set<String> _lowBatteryWarned = {};
  final Set<String> _offlineWarned = {};

  CameraHealthMonitor({required this.notify, this.enabled = true, DateTime Function()? now}) : _now = now ?? DateTime.now;

  Future<void> check(Iterable<CameraLink> cameras) async {
    final now = _now();
    for (final c in cameras) {
      final level = c.batteryLevel;
      if (c.isCharging == true || (level != null && level >= recoverPercent)) _lowBatteryWarned.remove(c.cameraId);
      if (c.controlConnected) _offlineWarned.remove(c.cameraId);
      if (!enabled) continue;

      if (c.controlConnected && level != null && level <= lowPercent && c.isCharging != true && _lowBatteryWarned.add(c.cameraId)) {
        await notify(
          id: _id('battery', c.cameraId),
          title: '🔋 ${c.deviceName}: battery low',
          body: '${level.round()}% left. Plug the camera phone in to keep it streaming.',
        );
      }
      final dropped = c.disconnectedAt;
      if (!c.controlConnected &&
          c.droppedWhileStreaming &&
          dropped != null &&
          now.difference(dropped) >= CameraLink.reconnectGrace &&
          _offlineWarned.add(c.cameraId)) {
        await notify(
          id: _id('offline', c.cameraId),
          title: '📴 ${c.deviceName} went offline',
          body: 'It stopped streaming ${_ago(now.difference(dropped))}. Check its Wi-Fi, battery, and that VYRO is open on it.',
        );
      }
    }
  }

  static int _id(String kind, String cameraId) => '$kind:$cameraId'.hashCode & 0x7fffffff;

  static String _ago(Duration d) => d.inMinutes < 1 ? 'a minute ago' : '${d.inMinutes} min ago';
}

/// "just now", "5 min ago", "2 h ago", "3 days ago".
String describeAgo(DateTime? at, [DateTime? now]) {
  if (at == null) return 'not yet';
  final d = (now ?? DateTime.now()).difference(at);
  if (d.inSeconds < 10) return 'just now';
  if (d.inMinutes < 1) return '${d.inSeconds}s ago';
  if (d.inHours < 1) return '${d.inMinutes} min ago';
  if (d.inDays < 1) return '${d.inHours} h ago';
  return d.inDays == 1 ? 'yesterday' : '${d.inDays} days ago';
}
