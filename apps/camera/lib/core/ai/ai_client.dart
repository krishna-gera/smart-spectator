import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

/// Where the AI proxy lives. The AI provider's key (Groq) is never in the app: only the proxy
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
/// The AI's precise reading of a plain-language watch task.
class TaskPlan {
  final String question;
  final bool targetVisible;
  final String advice;
  final bool progressApplicable;
  final String currentState;

  const TaskPlan({
    required this.question,
    required this.targetVisible,
    this.advice = '',
    this.progressApplicable = false,
    this.currentState = '',
  });

  factory TaskPlan.fromJson(Map<String, dynamic> j) => TaskPlan(
        question: j['question'] as String,
        targetVisible: j['target_visible'] as bool? ?? true,
        advice: j['advice'] as String? ?? '',
        progressApplicable: j['progress_applicable'] as bool? ?? false,
        currentState: j['current_state'] as String? ?? '',
      );
}

/// One answer to "is the watched condition met in this picture?".
class TaskCheck {
  final bool conditionMet;
  final double confidence;
  final int? progressPercent;
  final String observation;
  final bool targetVisible;

  const TaskCheck({
    required this.conditionMet,
    required this.confidence,
    this.progressPercent,
    this.observation = '',
    this.targetVisible = true,
  });

  factory TaskCheck.fromJson(Map<String, dynamic> j) => TaskCheck(
        conditionMet: j['condition_met'] as bool,
        confidence: (j['confidence'] as num?)?.toDouble() ?? 0,
        progressPercent: (j['progress_percent'] as num?)?.toInt(),
        observation: j['observation'] as String? ?? '',
        targetVisible: j['target_visible'] as bool? ?? true,
      );
}

/// Result of a proxy call: a value, or a readable error. [retryLater] is set
/// when the AI is rate-limited and the same request should simply wait.
class AiReply<T> {
  final T? value;
  final String? error;
  final bool retryLater;

  const AiReply.ok(T this.value)
      : error = null,
        retryLater = false;
  const AiReply.failed(String this.error, {this.retryLater = false}) : value = null;

  bool get ok => value != null;
}

class AiClient {
  final AiConfig config;
  final http.Client _http;

  AiClient(this.config, {http.Client? httpClient}) : _http = httpClient ?? http.Client();

  static const _messages = {
    'ai_not_authorised': 'The AI service rejected its API key (check the Groq key and account).',
    'daily_limit_reached': 'Daily AI limit reached.',
    'too_frequent': 'This camera was analysed moments ago.',
    'ai_rate_limited': 'The AI is busy; try again shortly.',
    'unauthorised': 'This app is not allowed to use the AI service.',
    'proxy_not_configured': 'The AI service is missing its key.',
  };

  Future<AiReply<TaskPlan>> planTask({
    required Uint8List jpeg,
    required String taskId,
    required String cameraName,
    required String task,
  }) =>
      _post('/v1/plan-task', {'image_jpeg_base64': base64Encode(jpeg), 'task_id': taskId, 'camera_name': cameraName, 'task': task},
          TaskPlan.fromJson);

  Future<AiReply<TaskCheck>> checkTask({
    required Uint8List jpeg,
    required String taskId,
    required String cameraName,
    required String task,
    required String question,
    String? previousObservation,
  }) =>
      _post(
          '/v1/check-task',
          {
            'image_jpeg_base64': base64Encode(jpeg),
            'task_id': taskId,
            'camera_name': cameraName,
            'task': task,
            'question': question,
            if (previousObservation != null && previousObservation.isNotEmpty) 'previous_observation': previousObservation,
          },
          TaskCheck.fromJson);

  Future<AiReply<T>> _post<T>(String path, Map<String, Object?> payload, T Function(Map<String, dynamic>) parse) async {
    final base = config.proxyUrl;
    if (!config.isConfigured || base == null) return const AiReply.failed('AI is not set up in this build.');
    try {
      final res = await _http
          .post(base.resolve(path),
              headers: {'Authorization': 'Bearer ${config.token}', 'Content-Type': 'application/json'}, body: jsonEncode(payload))
          .timeout(const Duration(seconds: 45));
      final body = jsonDecode(res.body);
      if (res.statusCode == 200 && body is Map) return AiReply.ok(parse(Map<String, dynamic>.from(body)));
      final code = body is Map ? body['error'] as String? : null;
      return AiReply.failed(_messages[code] ?? 'AI request failed (${res.statusCode}).',
          retryLater: code == 'ai_rate_limited' || code == 'too_frequent');
    } catch (_) {
      return const AiReply.failed('Could not reach the AI service.', retryLater: true);
    }
  }

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
