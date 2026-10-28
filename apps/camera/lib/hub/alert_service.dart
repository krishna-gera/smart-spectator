import 'dart:async';
import 'dart:typed_data';

import '../core/ai/ai_client.dart';
import 'event_store.dart';

typedef Notifier = Future<void> Function({required int id, required String title, required String body});

/// Decides what happens after a camera reports motion on the main phone:
/// optional AI analysis (per-camera opt-in), then at most one notification per
/// camera per [cooldown], worded with the AI's description when available.
class AlertService {
  final EventStore store;
  final AiClient ai;
  final Notifier notify;
  final Duration cooldown;

  /// How long a notification waits for the AI before going out without it.
  final Duration aiWait;
  final DateTime Function() _now;

  final Map<String, DateTime> _lastAlert = {};

  AlertService({
    required this.store,
    required this.ai,
    required this.notify,
    this.cooldown = const Duration(minutes: 1),
    this.aiWait = const Duration(seconds: 8),
    DateTime Function()? now,
  }) : _now = now ?? DateTime.now;

  static const categoryLabels = {
    'person': 'Person',
    'vehicle': 'Vehicle',
    'animal': 'Animal',
    'package': 'Package',
    'motion_other': 'Motion',
    'no_activity': 'No activity',
    'camera_problem': 'Camera problem',
  };

  bool aiAvailableFor(String cameraId) => ai.config.isConfigured && store.settingsFor(cameraId).aiEnabled;

  Future<void> onMotion(CameraEvent event) async {
    final settings = store.settingsFor(event.cameraId);
    AiResult? result;
    // Motion descriptions share the AI's per-minute picture budget with watch
    // tasks; when it is used up the alert goes out without a description.
    if (aiAvailableFor(event.cameraId) && ai.canSendPicture) {
      final file = store.snapshotOf(event);
      if (file != null && await file.exists()) {
        // The analysis keeps running (and saves its result) even if we stop waiting.
        final analysis = _analyzeInto(event, await file.readAsBytes());
        result = await analysis.timeout(aiWait, onTimeout: () => const AiResult.failed('AI is taking longer than usual.'));
      }
    }

    if (!settings.notify) return;
    if (result?.insight?.isQuiet ?? false) return; // AI saw nothing worth an alert.
    final now = _now();
    final last = _lastAlert[event.cameraId];
    if (last != null && now.difference(last) < cooldown) return;
    _lastAlert[event.cameraId] = now;

    final insight = result?.insight;
    final t = event.startedAt.toLocal();
    final hhmm = '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
    await notify(
      id: event.id.hashCode & 0x7fffffff,
      title: insight != null
          ? '${event.cameraName}: ${categoryLabels[insight.category] ?? 'Motion'}${insight.threatLevel == 'high' ? ' ⚠️' : ''}'
          : 'Motion · ${event.cameraName}',
      body: insight?.summary ?? 'Motion detected at $hhmm. Open VYRO to see the snapshot.',
    );
  }

  /// "Ask AI now": saves the snapshot as an event and records the AI's answer.
  Future<(CameraEvent, AiResult)> analyzeSnapshot({
    required String cameraId,
    required String cameraName,
    required Uint8List jpeg,
    int rotationDegrees = 0,
  }) async {
    final event = await store.startMotion(
      cameraId: cameraId,
      cameraName: cameraName,
      score: 0,
      rotationDegrees: rotationDegrees,
      snapshotJpeg: jpeg,
      type: 'ai_check',
    );
    await store.markSeen([event.id]);
    return (event, await _analyzeInto(event, jpeg));
  }

  Future<AiResult> _analyzeInto(CameraEvent event, Uint8List jpeg) async {
    final result = await ai.analyze(jpeg: jpeg, cameraId: event.cameraId, cameraName: event.cameraName);
    final i = result.insight;
    await store.setAiResult(event.id,
        summary: i?.summary, category: i?.category, threatLevel: i?.threatLevel, error: result.error);
    return result;
  }
}
