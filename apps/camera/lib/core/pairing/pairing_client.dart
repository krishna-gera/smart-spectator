import 'dart:convert';
import 'package:http/http.dart' as http;

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
  static Future<PairingResponse> requestPairing({
    required String hubIp,
    int hubPort = 8000,
    required String deviceId,
    required String deviceName,
  }) async {
    final url = Uri.parse('http://$hubIp:$hubPort/api/v1/devices/pair/request');
    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'device_id': deviceId,
          'device_name': deviceName,
          'device_model': 'Android Phone',
          'os_version': 'Android 14',
          'app_version': '1.0.0',
        }),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 202) {
        final data = jsonDecode(response.body);
        return PairingResponse(
          success: true,
          verificationCode: data['verification_code'],
          expiresInSeconds: data['expires_in_seconds'],
        );
      } else {
        return PairingResponse(
          success: false,
          errorMessage: 'Server rejected pairing request (${response.statusCode})',
        );
      }
    } catch (e) {
      return PairingResponse(
        success: false,
        errorMessage: 'Connection failed: $e',
      );
    }
  }

  static Future<PairingResponse> verifyPairing({
    required String hubIp,
    int hubPort = 8000,
    required String deviceId,
    required String pin,
  }) async {
    final url = Uri.parse('http://$hubIp:$hubPort/api/v1/devices/pair/verify');
    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'device_id': deviceId,
          'verification_code': pin.trim(),
        }),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return PairingResponse(
          success: true,
          deviceToken: data['device_token'],
          cameraId: data['camera_id'],
        );
      } else {
        final data = jsonDecode(response.body);
        return PairingResponse(
          success: false,
          errorMessage: data['detail'] ?? 'Verification failed',
        );
      }
    } catch (e) {
      return PairingResponse(
        success: false,
        errorMessage: 'Verification failed: $e',
      );
    }
  }
}
