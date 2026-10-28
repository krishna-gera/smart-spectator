import 'dart:convert';
import 'package:http/http.dart' as http;

/// A main phone's LAN address. Accepts "10.0.0.5" or "10.0.0.5:8000".
class HubAddress {
  static const int defaultPort = 8000;

  final String host;
  final int port;

  const HubAddress(this.host, [this.port = defaultPort]);

  /// Returns null when [input] is not a usable host[:port].
  static HubAddress? tryParse(String input) {
    final text = input.trim().replaceFirst(RegExp(r'^https?://'), '').replaceFirst(RegExp(r'/.*$'), '');
    if (text.isEmpty) return null;
    final parts = text.split(':');
    if (parts.length > 2) return null;
    final host = parts[0];
    if (!RegExp(r'^[A-Za-z0-9.\-]+$').hasMatch(host)) return null;
    final port = parts.length == 2 ? int.tryParse(parts[1]) : defaultPort;
    if (port == null || port < 1 || port > 65535) return null;
    return HubAddress(host, port);
  }

  Uri uri(String path) => Uri(scheme: 'http', host: host, port: port, path: path);

  @override
  String toString() => port == defaultPort ? host : '$host:$port';

  @override
  bool operator ==(Object other) => other is HubAddress && other.host == host && other.port == port;

  @override
  int get hashCode => Object.hash(host, port);
}

class PairingResponse {
  final bool success;
  final String? verificationCode;
  final int? expiresInSeconds;
  final String? deviceToken;
  final String? cameraId;
  final String? errorMessage;

  PairingResponse({
    required this.success,
    this.verificationCode,
    this.expiresInSeconds,
    this.deviceToken,
    this.cameraId,
    this.errorMessage,
  });
}

class PairingClient {
  static const _timeout = Duration(seconds: 5);

  /// One step: send the 6-digit code shown on the main phone, get a token.
  static Future<PairingResponse> pairWithCode({
    required HubAddress hub,
    required String deviceId,
    required String deviceName,
    required String code,
  }) =>
      _post(hub, '/api/v1/devices/pair/code', {
        'device_id': deviceId,
        'device_name': deviceName,
        'code': code.trim(),
      }, onSuccess: _paired);

  /// Legacy two-step flow, step 1: ask the main phone to show a per-device PIN.
  static Future<PairingResponse> requestPairing({
    required String hubIp,
    int hubPort = HubAddress.defaultPort,
    required String deviceId,
    required String deviceName,
  }) =>
      _post(HubAddress(hubIp, hubPort), '/api/v1/devices/pair/request', {
        'device_id': deviceId,
        'device_name': deviceName,
      }, okStatus: 202, onSuccess: (data) => PairingResponse(
            success: true,
            verificationCode: data['verification_code'] as String?,
            expiresInSeconds: (data['expires_in_seconds'] as num?)?.toInt(),
          ));

  /// Legacy two-step flow, step 2: send that PIN.
  static Future<PairingResponse> verifyPairing({
    required String hubIp,
    int hubPort = HubAddress.defaultPort,
    required String deviceId,
    required String pin,
  }) =>
      _post(HubAddress(hubIp, hubPort), '/api/v1/devices/pair/verify', {
        'device_id': deviceId,
        'verification_code': pin.trim(),
      }, onSuccess: _paired);

  static PairingResponse _paired(Map<String, dynamic> data) => PairingResponse(
        success: true,
        deviceToken: data['device_token'] as String?,
        cameraId: data['camera_id'] as String?,
      );

  /// Every failure (bad address, timeout, refused, HTTP error) becomes a
  /// readable error response; this never throws.
  static Future<PairingResponse> _post(
    HubAddress hub,
    String path,
    Map<String, Object?> body, {
    int okStatus = 200,
    required PairingResponse Function(Map<String, dynamic>) onSuccess,
  }) async {
    try {
      final response = await http
          .post(hub.uri(path), headers: {'Content-Type': 'application/json'}, body: jsonEncode(body))
          .timeout(_timeout);
      Map<String, dynamic> data = {};
      try {
        final decoded = jsonDecode(response.body);
        if (decoded is Map) data = Map<String, dynamic>.from(decoded);
      } catch (_) {}
      if (response.statusCode == okStatus) return onSuccess(data);
      final detail = data['detail'];
      return PairingResponse(
        success: false,
        errorMessage: detail is String ? detail : 'The main phone refused the request (${response.statusCode}).',
      );
    } catch (_) {
      return PairingResponse(
        success: false,
        errorMessage: 'Could not reach the main phone at $hub. Make sure Smart Spectator is open in View Mode.',
      );
    }
  }
}
