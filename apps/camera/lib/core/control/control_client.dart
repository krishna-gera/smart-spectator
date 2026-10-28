import 'dart:async';
import 'dart:convert';
import 'package:battery_plus/battery_plus.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

/// Camera phone side of the control channel: sends 1 Hz telemetry and acts on
/// commands from the main phone (e.g. "request_idr").
class ControlClient {
  final String hubIp;
  final int hubPort;
  final String deviceId;
  final String cameraId;
  final String deviceToken;

  /// Called for every command the main phone sends.
  final void Function(Map<String, dynamic> command)? onCommand;

  /// Camera sensor rotation in degrees (0/90/180/270) so the viewer can show
  /// the picture upright.
  final int sensorOrientation;

  /// Live rotation (0/90/180/270) when the camera phone can be turned while
  /// streaming; overrides [sensorOrientation].
  final int Function()? rotationProvider;

  /// Current measured capture FPS (null when not streaming).
  final double? Function()? fpsProvider;

  /// Called when the control channel connects or drops.
  final void Function(bool connected)? onConnectionChanged;

  /// Retry delays after a failed or dropped connection (the last repeats).
  static const retryDelays = [Duration(seconds: 2), Duration(seconds: 4), Duration(seconds: 8), Duration(seconds: 15)];
  int _failures = 0;

  WebSocketChannel? _channel;
  Timer? _telemetryTimer;
  Timer? _retryTimer;
  final _battery = Battery();
  bool _isRunning = false;

  ControlClient({
    required this.hubIp,
    required this.hubPort,
    required this.deviceId,
    required this.cameraId,
    required this.deviceToken,
    this.onCommand,
    this.sensorOrientation = 0,
    this.rotationProvider,
    this.fpsProvider,
    this.onConnectionChanged,
  });

  bool get isConnected => _channel != null;

  Future<void> start() async {
    if (_isRunning) return;
    _isRunning = true;
    await _connect();
  }

  /// Parses a control message; returns it only if it is a device command.
  static Map<String, dynamic>? parseCommand(Object? raw) {
    if (raw is! String) return null;
    try {
      final data = jsonDecode(raw);
      if (data is Map && data['type'] == 'device_control_command' && data['action'] is String) {
        return Map<String, dynamic>.from(data);
      }
    } catch (_) {}
    return null;
  }

  Future<void> _connect() async {
    if (!_isRunning) return;
    final wsUrl = Uri.parse('ws://$hubIp:$hubPort/api/v1/control/ws?token=$deviceToken');

    try {
      final channel = WebSocketChannel.connect(wsUrl);
      await channel.ready;
      if (!_isRunning) {
        await channel.sink.close();
        return;
      }
      _channel = channel;
      _failures = 0;
      onConnectionChanged?.call(true);
      _startTelemetryLoop();

      channel.stream.listen(
        (data) {
          final cmd = parseCommand(data);
          if (cmd == null) return;
          onCommand?.call(cmd);
          channel.sink.add(jsonEncode({
            'protocol': 'ss_control_v1',
            'type': 'command_ack',
            'action': cmd['action'],
          }));
        },
        onDone: _retry,
        onError: (_) => _retry(),
        cancelOnError: true,
      );
    } catch (_) {
      _retry();
    }
  }

  void _startTelemetryLoop() {
    _telemetryTimer?.cancel();
    _telemetryTimer = Timer.periodic(const Duration(seconds: 1), (timer) async {
      if (_channel == null) return;

      int? batteryLevel;
      bool? isCharging;
      try {
        batteryLevel = await _battery.batteryLevel;
        final state = await _battery.batteryState;
        isCharging = state == BatteryState.charging || state == BatteryState.full;
      } catch (_) {}

      final report = {
        'protocol': 'ss_control_v1',
        'type': 'telemetry_report',
        'camera_id': cameraId,
        'device_id': deviceId,
        'timestamp': DateTime.now().millisecondsSinceEpoch,
        'metrics': {
          'battery_level_percent': batteryLevel?.toDouble(),
          'is_charging': isCharging,
          'battery_temperature_c': null,
          'encoder_fps': fpsProvider?.call(),
          'sensor_orientation': rotationProvider?.call() ?? sensorOrientation,
          'uptime_seconds': timer.tick,
        }
      };

      try {
        _channel?.sink.add(jsonEncode(report));
      } catch (_) {}
    });
  }

  void _retry() {
    final wasConnected = _channel != null;
    _channel = null;
    _telemetryTimer?.cancel();
    _retryTimer?.cancel();
    if (wasConnected) onConnectionChanged?.call(false);
    if (_isRunning) {
      final delay = retryDelays[_failures.clamp(0, retryDelays.length - 1)];
      _failures++;
      _retryTimer = Timer(delay, _connect);
    }
  }

  void stop() {
    _isRunning = false;
    _telemetryTimer?.cancel();
    _retryTimer?.cancel();
    _channel?.sink.close();
    final wasConnected = _channel != null;
    _channel = null;
    _failures = 0;
    if (wasConnected) onConnectionChanged?.call(false);
  }
}
