import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import '../core/ai/ai_client.dart';
import '../core/motion/motion_detector.dart';
import 'alert_service.dart';
import 'event_store.dart';
import 'hub_server.dart';

enum TaskStatus { watching, paused, done, stopped, expired }

/// A plain-language job given to the AI for one camera, e.g. "tell me when the
/// water reaches the MAX line".
class WatchTask {
  final String id;
  final String cameraId;
  String cameraName;
  final String description;

  /// The AI's precise yes/no reading of [description] (set on the first check).
  String? question;
  String? advice;
  bool progressApplicable;

  int intervalSeconds;
  bool remindUntilAck;
  bool keepWatching;
  int autoStopMinutes;

  TaskStatus status;
  final DateTime createdAt;
  DateTime startedAt;
  DateTime? completedAt;
  DateTime? acknowledgedAt;
  DateTime? lastCheckAt;
  DateTime? lastAiCheckAt;
  DateTime? lastReminderAt;
  DateTime? retryAfter;

  String? lastObservation;
  int? lastProgress;
  String? lastError;
  int consecutiveMet;

  /// After a "keep watching" alert, wait for the condition to clear first.
  bool waitingForReset;
  int aiChecks;
  int skippedChecks;
  int remindersSent;
  String? lastGrid;
  String? doneEventId;

  WatchTask({
    required this.id,
    required this.cameraId,
    required this.cameraName,
    required this.description,
    this.question,
    this.advice,
    this.progressApplicable = false,
    this.intervalSeconds = 30,
    this.remindUntilAck = true,
    this.keepWatching = false,
    this.autoStopMinutes = 180,
    this.status = TaskStatus.watching,
    required this.createdAt,
    required this.startedAt,
    this.completedAt,
    this.acknowledgedAt,
    this.lastCheckAt,
    this.lastAiCheckAt,
    this.lastReminderAt,
    this.retryAfter,
    this.lastObservation,
    this.lastProgress,
    this.lastError,
    this.consecutiveMet = 0,
    this.waitingForReset = false,
    this.aiChecks = 0,
    this.skippedChecks = 0,
    this.remindersSent = 0,
    this.lastGrid,
    this.doneEventId,
  });

  bool get isActive => status == TaskStatus.watching;
  bool get needsAcknowledgement => status == TaskStatus.done && remindUntilAck && acknowledgedAt == null;

  Map<String, dynamic> toJson() => {
        'id': id,
        'camera_id': cameraId,
        'camera_name': cameraName,
        'description': description,
        'question': question,
        'advice': advice,
        'progress_applicable': progressApplicable,
        'interval_seconds': intervalSeconds,
        'remind_until_ack': remindUntilAck,
        'keep_watching': keepWatching,
        'auto_stop_minutes': autoStopMinutes,
        'status': status.name,
        'created_at': createdAt.toIso8601String(),
        'started_at': startedAt.toIso8601String(),
        'completed_at': completedAt?.toIso8601String(),
        'acknowledged_at': acknowledgedAt?.toIso8601String(),
        'last_check_at': lastCheckAt?.toIso8601String(),
        'last_ai_check_at': lastAiCheckAt?.toIso8601String(),
        'last_reminder_at': lastReminderAt?.toIso8601String(),
        'last_observation': lastObservation,
        'last_progress': lastProgress,
        'last_error': lastError,
        'consecutive_met': consecutiveMet,
        'waiting_for_reset': waitingForReset,
        'ai_checks': aiChecks,
        'skipped_checks': skippedChecks,
        'reminders_sent': remindersSent,
        'last_grid': lastGrid,
        'done_event_id': doneEventId,
      };

  static DateTime? _date(Object? v) => v is String ? DateTime.tryParse(v) : null;

  factory WatchTask.fromJson(Map<String, dynamic> j) => WatchTask(
        id: j['id'] as String,
        cameraId: j['camera_id'] as String,
        cameraName: j['camera_name'] as String? ?? 'Camera',
        description: j['description'] as String,
        question: j['question'] as String?,
        advice: j['advice'] as String?,
        progressApplicable: j['progress_applicable'] as bool? ?? false,
        intervalSeconds: (j['interval_seconds'] as num?)?.toInt() ?? 30,
        remindUntilAck: j['remind_until_ack'] as bool? ?? true,
        keepWatching: j['keep_watching'] as bool? ?? false,
        autoStopMinutes: (j['auto_stop_minutes'] as num?)?.toInt() ?? 180,
        status: TaskStatus.values.firstWhere((s) => s.name == j['status'], orElse: () => TaskStatus.stopped),
        createdAt: _date(j['created_at']) ?? DateTime.now(),
        startedAt: _date(j['started_at']) ?? DateTime.now(),
        completedAt: _date(j['completed_at']),
        acknowledgedAt: _date(j['acknowledged_at']),
        lastCheckAt: _date(j['last_check_at']),
        lastAiCheckAt: _date(j['last_ai_check_at']),
        lastReminderAt: _date(j['last_reminder_at']),
        lastObservation: j['last_observation'] as String?,
        lastProgress: (j['last_progress'] as num?)?.toInt(),
        lastError: j['last_error'] as String?,
        consecutiveMet: (j['consecutive_met'] as num?)?.toInt() ?? 0,
        waitingForReset: j['waiting_for_reset'] as bool? ?? false,
        aiChecks: (j['ai_checks'] as num?)?.toInt() ?? 0,
        skippedChecks: (j['skipped_checks'] as num?)?.toInt() ?? 0,
        remindersSent: (j['reminders_sent'] as num?)?.toInt() ?? 0,
        lastGrid: j['last_grid'] as String?,
        doneEventId: j['done_event_id'] as String?,
      );
}

/// Watch tasks saved on the main phone (tasks.json next to the event history).
class TaskStore {
  final File file;
  final List<WatchTask> _tasks = [];
  Future<void> _writes = Future.value();

  TaskStore(Directory dir) : file = File('${dir.path}/tasks.json');

  List<WatchTask> get tasks => List.unmodifiable(_tasks);
  WatchTask? byId(String id) => _tasks.where((t) => t.id == id).firstOrNull;

  Future<void> load() async {
    _tasks.clear();
    if (!await file.exists()) return;
    try {
      final raw = jsonDecode(await file.readAsString()) as List;
      _tasks.addAll(raw.map((e) => WatchTask.fromJson(Map<String, dynamic>.from(e as Map))));
    } catch (_) {}
  }

  Future<void> add(WatchTask t) {
    _tasks.insert(0, t);
    return save();
  }

  Future<void> remove(String id) {
    _tasks.removeWhere((t) => t.id == id);
    return save();
  }

  /// Serialised atomic write (temp file + rename).
  Future<void> save() {
    final data = jsonEncode(_tasks.map((t) => t.toJson()).toList());
    final next = _writes.then((_) async {
      await file.parent.create(recursive: true);
      final tmp = File('${file.path}.tmp');
      await tmp.writeAsString(data, flush: true);
      await tmp.rename(file.path);
    });
    _writes = next.catchError((_) {});
    return next;
  }
}

/// Runs watch tasks on the main phone: periodic snapshots, skip when the scene
/// is unchanged, AI check, two confirmations, alert, reminders, auto-stop.
class TaskWatcher {
  static const confirmationsNeeded = 2;
  static const minConfidence = 0.6;

  /// Share of the picture that must change before another AI check is spent.
  static const minSceneChange = 0.01;
  static const reminderEvery = Duration(minutes: 2);
  static const maxReminders = 30;
  static const retryDelay = Duration(seconds: 30);
  static const intervals = [15, 30, 60, 300];

  final TaskStore store;
  final EventStore events;
  final AiClient ai;
  final Future<CameraSnapshot?> Function(String cameraId) snapshot;
  final int Function(String cameraId) rotationOf;
  final Notifier notify;

  /// Active task descriptions per camera changed (drives the camera's badge).
  final void Function(String cameraId, List<String> descriptions) onWatchChanged;
  final DateTime Function() _now;
  final Random _random = Random.secure();

  final Set<String> _inFlight = {};
  final _changes = StreamController<void>.broadcast();
  Timer? _timer;

  TaskWatcher({
    required this.store,
    required this.events,
    required this.ai,
    required this.snapshot,
    required this.notify,
    required this.onWatchChanged,
    int Function(String cameraId)? rotationOf,
    DateTime Function()? now,
  })  : rotationOf = rotationOf ?? ((_) => 0),
        _now = now ?? DateTime.now;

  Stream<void> get changes => _changes.stream;
  bool get aiAvailable => ai.config.isConfigured;

  void start() {
    _timer ??= Timer.periodic(const Duration(seconds: 1), (_) => tick());
    for (final cameraId in store.tasks.map((t) => t.cameraId).toSet()) {
      _announce(cameraId);
    }
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
  }

  void dispose() {
    stop();
    _changes.close();
  }

  // ---------------------------------------------------------------- task actions

  Future<WatchTask> create({
    required String cameraId,
    required String cameraName,
    required String description,
    int intervalSeconds = 30,
    bool remindUntilAck = true,
    bool keepWatching = false,
    int autoStopMinutes = 180,
    TaskPlan? plan,
  }) async {
    final now = _now();
    final task = WatchTask(
      id: 'task_${now.millisecondsSinceEpoch}_${_random.nextInt(1 << 20).toRadixString(16)}',
      cameraId: cameraId,
      cameraName: cameraName,
      description: description.trim(),
      question: plan?.question,
      advice: plan?.advice,
      progressApplicable: plan?.progressApplicable ?? false,
      lastObservation: plan?.currentState,
      intervalSeconds: intervalSeconds,
      remindUntilAck: remindUntilAck,
      keepWatching: keepWatching,
      autoStopMinutes: autoStopMinutes,
      createdAt: now,
      startedAt: now,
    );
    await store.add(task);
    _announce(cameraId);
    return task;
  }

  /// "Test now": how the AI understands the task for the current picture.
  Future<AiReply<TaskPlan>> preview({required String cameraId, required String cameraName, required String description}) async {
    final snap = await snapshot(cameraId);
    if (snap == null) return const AiReply.failed('The camera did not send a picture. Is it streaming?');
    return ai.planTask(jpeg: snap.jpeg, taskId: 'preview_$cameraId', cameraName: cameraName, task: description.trim());
  }

  Future<void> pause(WatchTask t) => _set(t, TaskStatus.paused);
  Future<void> stopTask(WatchTask t) => _set(t, TaskStatus.stopped);

  Future<void> resume(WatchTask t) async {
    t
      ..startedAt = _now()
      ..consecutiveMet = 0
      ..waitingForReset = false
      ..completedAt = null
      ..acknowledgedAt = null
      ..remindersSent = 0
      ..lastError = null;
    await _set(t, TaskStatus.watching);
  }

  Future<void> acknowledge(WatchTask t) async {
    t.acknowledgedAt = _now();
    await store.save();
    _changed();
  }

  Future<void> delete(WatchTask t) async {
    await store.remove(t.id);
    _announce(t.cameraId);
  }

  Future<void> _set(WatchTask t, TaskStatus s) async {
    t.status = s;
    await store.save();
    _announce(t.cameraId);
  }

  // ---------------------------------------------------------------- scheduling

  Future<void> tick() async {
    final now = _now();
    for (final t in store.tasks) {
      if (t.status == TaskStatus.watching) {
        if (now.difference(t.startedAt) >= Duration(minutes: t.autoStopMinutes)) {
          await _expire(t);
          continue;
        }
        final due = t.lastCheckAt == null || now.difference(t.lastCheckAt!) >= Duration(seconds: t.intervalSeconds);
        final retryOk = t.retryAfter == null || !now.isBefore(t.retryAfter!);
        if (due && retryOk && !_inFlight.contains(t.id)) await checkNow(t);
      } else if (t.needsAcknowledgement && t.remindersSent < maxReminders) {
        final last = t.lastReminderAt ?? t.completedAt;
        if (last != null && now.difference(last) >= reminderEvery) await _remind(t);
      }
    }
  }

  /// One check of [t] (also used directly by tests).
  Future<void> checkNow(WatchTask t) async {
    if (!_inFlight.add(t.id)) return;
    try {
      final now = _now();
      t.lastCheckAt = now;
      final snap = await snapshot(t.cameraId);
      if (snap == null) {
        t.lastError = 'Waiting for the camera to stream.';
        return;
      }

      // First check: turn the owner's words into a precise question.
      if (t.question == null) {
        final plan = await ai.planTask(jpeg: snap.jpeg, taskId: t.id, cameraName: t.cameraName, task: t.description);
        if (!plan.ok) {
          _failed(t, plan.error!, plan.retryLater);
          return;
        }
        final p = plan.value!;
        t
          ..question = p.question
          ..advice = p.advice
          ..progressApplicable = p.progressApplicable
          ..lastObservation = p.currentState
          ..lastError = p.targetVisible ? null : (p.advice.isEmpty ? 'The AI cannot see what to watch.' : p.advice);
        return; // The actual check runs on the next interval.
      }

      // Skip the AI when the picture has not changed since its last look.
      final grid = snap.grid;
      if (grid != null && t.lastGrid != null && t.consecutiveMet == 0) {
        final previous = base64Decode(t.lastGrid!);
        if (MotionDetector.gridChange(previous, grid) < minSceneChange) {
          t.skippedChecks++;
          return;
        }
      }

      final reply = await ai.checkTask(
        jpeg: snap.jpeg,
        taskId: t.id,
        cameraName: t.cameraName,
        task: t.description,
        question: t.question!,
        previousObservation: t.lastObservation,
      );
      if (!reply.ok) {
        _failed(t, reply.error!, reply.retryLater);
        return;
      }
      final c = reply.value!;
      t
        ..aiChecks += 1
        ..lastAiCheckAt = now
        ..retryAfter = null
        ..lastObservation = c.observation.isEmpty ? t.lastObservation : c.observation
        ..lastProgress = c.progressPercent ?? t.lastProgress
        ..lastError = c.targetVisible ? null : 'The AI cannot see what to watch. ${t.advice ?? ''}'.trim()
        ..lastGrid = grid == null ? t.lastGrid : base64Encode(grid);

      final met = c.conditionMet && c.targetVisible && c.confidence >= minConfidence;
      if (!met) {
        t
          ..consecutiveMet = 0
          ..waitingForReset = false;
        return;
      }
      t.consecutiveMet++;
      if (t.consecutiveMet >= confirmationsNeeded && !t.waitingForReset) {
        await _complete(t, snap, c);
      }
    } finally {
      _inFlight.remove(t.id);
      await store.save();
      _changed();
    }
  }

  void _failed(WatchTask t, String error, bool retryLater) {
    t.lastError = error;
    if (retryLater) t.retryAfter = _now().add(retryDelay);
  }

  Future<void> _complete(WatchTask t, CameraSnapshot snap, TaskCheck c) async {
    final now = _now();
    final event = await events.startMotion(
      cameraId: t.cameraId,
      cameraName: t.cameraName,
      score: 1,
      rotationDegrees: rotationOf(t.cameraId),
      snapshotJpeg: snap.jpeg,
      type: 'task_done',
    );
    await events.setAiResult(event.id, summary: '${t.description} — ${c.observation}', category: 'task_done', threatLevel: 'none');
    t
      ..doneEventId = event.id
      ..completedAt = now
      ..lastReminderAt = now
      ..acknowledgedAt = null
      ..remindersSent = 0
      ..lastProgress = t.progressApplicable ? 100 : t.lastProgress;
    if (t.keepWatching) {
      t
        ..waitingForReset = true
        ..consecutiveMet = 0;
    } else {
      t.status = TaskStatus.done;
      _announce(t.cameraId);
    }
    await notify(
      id: t.id.hashCode & 0x7fffffff,
      title: '✅ ${t.cameraName}: done',
      body: '${c.observation.isEmpty ? t.description : c.observation} (${t.description})',
    );
  }

  Future<void> _remind(WatchTask t) async {
    t
      ..lastReminderAt = _now()
      ..remindersSent += 1;
    await store.save();
    await notify(
      id: t.id.hashCode & 0x7fffffff,
      title: '🔔 Reminder · ${t.cameraName}',
      body: '${t.description} — still waiting for you. Open Smart Spectator to mark it handled.',
    );
    _changed();
  }

  Future<void> _expire(WatchTask t) async {
    t.status = TaskStatus.expired;
    await store.save();
    _announce(t.cameraId);
    await notify(
      id: t.id.hashCode & 0x7fffffff,
      title: 'Stopped watching · ${t.cameraName}',
      body: '"${t.description}" did not happen within ${t.autoStopMinutes ~/ 60} h. Resume it if you still need it.',
    );
  }

  void _announce(String cameraId) {
    onWatchChanged(cameraId, [
      for (final t in store.tasks.where((t) => t.cameraId == cameraId && t.isActive)) t.description,
    ]);
    _changed();
  }

  void _changed() {
    if (!_changes.isClosed) _changes.add(null);
  }
}

/// Short status line for a task, shared by the app and the dashboard.
String describeTaskStatus(WatchTask t, DateTime now) {
  String ago(DateTime? d) {
    if (d == null) return 'not yet';
    final s = now.difference(d).inSeconds;
    if (s < 60) return '${s}s ago';
    if (s < 3600) return '${s ~/ 60} min ago';
    return '${s ~/ 3600} h ago';
  }

  return switch (t.status) {
    TaskStatus.watching when t.question == null => 'Understanding the task…',
    TaskStatus.watching => 'Watching · AI checked ${ago(t.lastAiCheckAt)}',
    TaskStatus.paused => 'Paused',
    TaskStatus.done => t.needsAcknowledgement ? 'Done · tap "Handled" to stop reminders' : 'Done',
    TaskStatus.stopped => 'Stopped',
    TaskStatus.expired => 'Stopped after ${t.autoStopMinutes ~/ 60} h',
  };
}
