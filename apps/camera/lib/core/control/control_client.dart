import 'dart:async';
import 'dart:convert';
import 'package:battery_plus/battery_plus.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class ControlClient {
  final String hubIp;
  final int hubPort;
  final String deviceId;
  final String cameraId;
  final String deviceToken;

  WebSocketChannel? _channel;
  Timer? _telemetryTimer;
  final _battery = Battery();
  bool _isRunning = false;

  ControlClient({
    required this.hubIp,
    required this.hubPort,
    required this.deviceId,
    required this.cameraId,
    required this.deviceToken,
  });

  Future<void> start() async {
    _isRunning = true;
    _connect();
  }

  void _connect() {
    if (!_isRunning) return;
    final wsUrl = Uri.parse(
      'ws://$hubIp:$hubPort/api/v1/control/ws?token=$deviceToken'
    );

    try {
      _channel = WebSocketChannel.connect(wsUrl);
      _startTelemetryLoop();

      _channel!.stream.listen(
        (data) {
          // Process Hub control commands (e.g. request_idr)
        },
        onDone: () => _retry(),
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

      int batteryLevel = 85;
      bool isCharging = false;
      try {
        batteryLevel = await _battery.batteryLevel;
        final state = await _battery.batteryState;
        isCharging = state == BatteryState.charging;
      } catch (_) {}

      final report = {
        'protocol': 'ss_control_v1',
        'type': 'telemetry_report',
        'camera_id': cameraId,
        'device_id': deviceId,
        'timestamp': DateTime.now().millisecondsSinceEpoch,
        'metrics': {
          'battery_level_percent': batteryLevel.toDouble(),
          'is_charging': isCharging,
          'battery_temperature_c': 34.5,
          'encoder_fps': 30.0,
          'uptime_seconds': timer.tick,
        }
      };

      try {
        _channel?.sink.add(jsonEncode(report));
      } catch (_) {}
    });
  }

  void _retry() {
    _channel = null;
    _telemetryTimer?.cancel();
    if (_isRunning) {
      Timer(const Duration(seconds: 3), () => _connect());
    }
  }

  void stop() {
    _isRunning = false;
    _telemetryTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
  }
}
