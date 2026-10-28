import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

/// Where the AI proxy lives. The xAI key is never in the app: only the proxy
/// address and a proxy access token, supplied at build time with
///   --dart-define=AI_PROXY_URL=http://10.0.0.5:8787
///   --dart-define=AI_PROXY_TOKEN=...
class AiConfig {
  final Uri? proxyUrl;
  final String token;

  const AiConfig({this.proxyUrl, this.token = ''});

  factory AiConfig.fromEnvironment() {
    const url = String.fromEnvironment('AI_PROXY_URL');
    const token = String.fromEnvironment('AI_PROXY_TOKEN');
    return AiConfig(proxyUrl: url.isEmpty ? null : Uri.tryParse(url), token: token);
  }

  bool get isConfigured => proxyUrl != null && token.isNotEmpty;
}

/// Structured description of a snapshot, as returned by the proxy.
class AiInsight {
  final String summary;
  final String category;
  final String threatLevel;
  final int peopleCount;
  final double confidence;
  final String model;

  const AiInsight({
    required this.summary,
    required this.category,
    required this.threatLevel,
    required this.peopleCount,
    required this.confidence,
    this.model = '',
  });

  factory AiInsight.fromJson(Map<String, dynamic> j) => AiInsight(
        summary: j['summary'] as String,
        category: j['category'] as String? ?? 'motion_other',
        threatLevel: j['threat_level'] as String? ?? 'none',
        peopleCount: (j['people_count'] as num?)?.toInt() ?? 0,
        confidence: (j['confidence'] as num?)?.toDouble() ?? 0,
        model: j['model'] as String? ?? '',
      );

  /// Nothing worth alerting about (shadows, lighting, empty scene).
  bool get isQuiet => category == 'no_activity';
}

class AiResult {
  final AiInsight? insight;

  /// Short reason shown to the user when [insight] is null.
  final String? error;

  const AiResult.ok(AiInsight this.insight) : error = null;
  const AiResult.failed(String this.error) : insight = null;

  bool get ok => insight != null;
}

/// Sends one JPEG to the AI proxy. Never throws.
class AiClient {
  final AiConfig config;
  final http.Client _http;

  AiClient(this.config, {http.Client? httpClient}) : _http = httpClient ?? http.Client();

  static const _messages = {
    'ai_not_authorised': 'The AI service is not active (check the xAI account has credits).',
    'daily_limit_reached': 'Daily AI limit reached.',
    'too_frequent': 'This camera was analysed moments ago.',
    'ai_rate_limited': 'The AI is busy; try again shortly.',
    'unauthorised': 'This app is not allowed to use the AI service.',
    'proxy_not_configured': 'The AI service is missing its key.',
  };

  Future<AiResult> analyze({required Uint8List jpeg, required String cameraId, required String cameraName}) async {
    final base = config.proxyUrl;
    if (!config.isConfigured || base == null) return const AiResult.failed('AI is not set up in this build.');
    try {
      final res = await _http
          .post(
            base.resolve('/v1/analyze'),
            headers: {'Authorization': 'Bearer ${config.token}', 'Content-Type': 'application/json'},
            body: jsonEncode({'image_jpeg_base64': base64Encode(jpeg), 'camera_id': cameraId, 'camera_name': cameraName}),
          )
          .timeout(const Duration(seconds: 45));
      final body = jsonDecode(res.body);
      if (res.statusCode == 200 && body is Map) {
        return AiResult.ok(AiInsight.fromJson(Map<String, dynamic>.from(body)));
      }
      final code = body is Map ? body['error'] as String? : null;
      return AiResult.failed(_messages[code] ?? 'AI request failed (${res.statusCode}).');
    } catch (_) {
      return const AiResult.failed('Could not reach the AI service.');
    }
  }
}
