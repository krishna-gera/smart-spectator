import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../pairing/pairing_client.dart';

/// Sends motion start/end from a camera phone to its main phone.
/// Never throws: a lost report must not interrupt streaming.
class MotionReporter {
  final HubAddress hub;
  final String deviceToken;

  MotionReporter({required this.hub, required this.deviceToken});

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $deviceToken',
      };

  /// Returns the main phone's event id, or null if the report failed or the
  /// main phone has motion detection switched off for this camera.
  Future<String?> started({required double score, Uint8List? snapshotJpeg}) async {
    try {
      final res = await http
          .post(hub.uri('/api/v1/events/motion'),
              headers: _headers,
              body: jsonEncode({
                'phase': 'started',
                'score': score,
                if (snapshotJpeg != null) 'snapshot_jpeg': base64Encode(snapshotJpeg),
              }))
          .timeout(const Duration(seconds: 8));
      if (res.statusCode != 201) return null;
      return (jsonDecode(res.body) as Map)['event_id'] as String?;
    } catch (_) {
      return null;
    }
  }

  /// Answers a main phone's "capture_snapshot" request ("Ask AI now").
  Future<bool> uploadSnapshot({required String requestId, required Uint8List jpeg}) async {
    try {
      final res = await http
          .post(hub.uri('/api/v1/snapshots'),
              headers: _headers, body: jsonEncode({'request_id': requestId, 'snapshot_jpeg': base64Encode(jpeg)}))
          .timeout(const Duration(seconds: 8));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<bool> ended({required String eventId, required double peakScore}) async {
    try {
      final res = await http
          .post(hub.uri('/api/v1/events/motion'),
              headers: _headers, body: jsonEncode({'phase': 'ended', 'event_id': eventId, 'peak_score': peakScore}))
          .timeout(const Duration(seconds: 5));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
