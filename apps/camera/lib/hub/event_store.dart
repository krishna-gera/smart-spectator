import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

/// Something a camera reported (Phase 3: motion). [aiSummary] is filled in
/// later by the xAI integration (Phase 4).
class CameraEvent {
  final String id;
  final String cameraId;
  final String cameraName;
  final String type;
  final DateTime startedAt;
  DateTime? endedAt;
  double peakScore;
  final String? snapshotFile;
  final int rotationDegrees;
  bool seen;
  String? aiSummary;
  String? aiCategory;
  String? aiThreatLevel;

  /// Why AI analysis did not happen (e.g. "AI limit reached"); null if it did or was not requested.
  String? aiError;

  CameraEvent({
    required this.id,
    required this.cameraId,
    required this.cameraName,
    required this.type,
    required this.startedAt,
    this.endedAt,
    this.peakScore = 0,
    this.snapshotFile,
    this.rotationDegrees = 0,
    this.seen = false,
    this.aiSummary,
    this.aiCategory,
    this.aiThreatLevel,
    this.aiError,
  });

  bool get isOngoing => endedAt == null;
  Duration? get duration => endedAt?.difference(startedAt);

  Map<String, dynamic> toJson() => {
        'id': id,
        'camera_id': cameraId,
        'camera_name': cameraName,
        'type': type,
        'started_at': startedAt.toIso8601String(),
        'ended_at': endedAt?.toIso8601String(),
        'peak_score': peakScore,
        'snapshot_file': snapshotFile,
        'rotation_degrees': rotationDegrees,
        'seen': seen,
        'ai_summary': aiSummary,
        'ai_category': aiCategory,
        'ai_threat_level': aiThreatLevel,
        'ai_error': aiError,
      };

  factory CameraEvent.fromJson(Map<String, dynamic> j) => CameraEvent(
        id: j['id'] as String,
        cameraId: j['camera_id'] as String,
        cameraName: j['camera_name'] as String? ?? 'Camera',
        type: j['type'] as String? ?? 'motion',
        startedAt: DateTime.parse(j['started_at'] as String),
        endedAt: j['ended_at'] == null ? null : DateTime.parse(j['ended_at'] as String),
        peakScore: (j['peak_score'] as num?)?.toDouble() ?? 0,
        snapshotFile: j['snapshot_file'] as String?,
        rotationDegrees: (j['rotation_degrees'] as num?)?.toInt() ?? 0,
        seen: j['seen'] as bool? ?? false,
        aiSummary: j['ai_summary'] as String?,
        aiCategory: j['ai_category'] as String?,
        aiThreatLevel: j['ai_threat_level'] as String?,
        aiError: j['ai_error'] as String?,
      );
}

/// Per-camera choices made on the main phone.
class CameraSettings {
  final bool motionEnabled;
  final double sensitivity;
  final bool notify;

  /// Send motion snapshots to the AI service (xAI). Off until the user opts in.
  final bool aiEnabled;

  const CameraSettings({this.motionEnabled = true, this.sensitivity = 0.5, this.notify = true, this.aiEnabled = false});

  CameraSettings copyWith({bool? motionEnabled, double? sensitivity, bool? notify, bool? aiEnabled}) => CameraSettings(
        motionEnabled: motionEnabled ?? this.motionEnabled,
        sensitivity: sensitivity ?? this.sensitivity,
        notify: notify ?? this.notify,
        aiEnabled: aiEnabled ?? this.aiEnabled,
      );

  Map<String, dynamic> toJson() =>
      {'motion_enabled': motionEnabled, 'sensitivity': sensitivity, 'notify': notify, 'ai_enabled': aiEnabled};

  factory CameraSettings.fromJson(Map<String, dynamic> j) => CameraSettings(
        motionEnabled: j['motion_enabled'] as bool? ?? true,
        sensitivity: ((j['sensitivity'] as num?)?.toDouble() ?? 0.5).clamp(0.0, 1.0),
        notify: j['notify'] as bool? ?? true,
        aiEnabled: j['ai_enabled'] as bool? ?? false,
      );
}

/// Event history on the main phone: a JSON index plus one JPEG per event.
/// Works offline; old events are pruned by age and count.
class EventStore {
  final Directory dir;
  final int maxEvents;
  final Duration retention;
  final DateTime Function() _now;
  final Random _random = Random.secure();

  final List<CameraEvent> _events = []; // newest first
  final Map<String, CameraSettings> _settings = {};
  Future<void> _writeQueue = Future.value();

  EventStore({
    required this.dir,
    this.maxEvents = 500,
    this.retention = const Duration(days: 7),
    DateTime Function()? now,
  }) : _now = now ?? DateTime.now;

  Directory get _snapshotDir => Directory('${dir.path}/snapshots');
  File get _eventsFile => File('${dir.path}/events.json');
  File get _settingsFile => File('${dir.path}/camera_settings.json');

  List<CameraEvent> get events => List.unmodifiable(_events);
  int get unseenCount => _events.where((e) => !e.seen).length;

  Future<void> load() async {
    await _snapshotDir.create(recursive: true);
    _events
      ..clear()
      ..addAll(await _readList(_eventsFile, CameraEvent.fromJson));
    _events.sort((a, b) => b.startedAt.compareTo(a.startedAt));
    if (await _settingsFile.exists()) {
      try {
        final raw = jsonDecode(await _settingsFile.readAsString()) as Map;
        raw.forEach((k, v) => _settings[k as String] = CameraSettings.fromJson(Map<String, dynamic>.from(v as Map)));
      } catch (_) {}
    }
    await _prune();
  }

  CameraSettings settingsFor(String cameraId) => _settings[cameraId] ?? const CameraSettings();

  Future<void> updateSettings(String cameraId, CameraSettings settings) async {
    _settings[cameraId] = settings;
    await _enqueue(() => _writeJson(_settingsFile, _settings.map((k, v) => MapEntry(k, v.toJson()))));
  }

  File? snapshotOf(CameraEvent e) => e.snapshotFile == null ? null : File('${_snapshotDir.path}/${e.snapshotFile}');

  CameraEvent? byId(String id) => _events.where((e) => e.id == id).firstOrNull;

  Future<CameraEvent> startMotion({
    required String cameraId,
    required String cameraName,
    required double score,
    int rotationDegrees = 0,
    Uint8List? snapshotJpeg,
    String type = 'motion',
  }) async {
    final id = 'ev_${_now().millisecondsSinceEpoch}_${_random.nextInt(1 << 20).toRadixString(16)}';
    String? fileName;
    if (snapshotJpeg != null && snapshotJpeg.isNotEmpty) {
      fileName = '$id.jpg';
      await File('${_snapshotDir.path}/$fileName').writeAsBytes(snapshotJpeg, flush: true);
    }
    final event = CameraEvent(
      id: id,
      cameraId: cameraId,
      cameraName: cameraName,
      type: type,
      startedAt: _now(),
      endedAt: type == 'motion' ? null : _now(),
      peakScore: score,
      snapshotFile: fileName,
      rotationDegrees: rotationDegrees,
    );
    _events.insert(0, event);
    await _prune();
    await _persist();
    return event;
  }

  /// Closes an event; only the camera that started it may end it.
  Future<CameraEvent?> endMotion({required String eventId, required String cameraId, double? peakScore}) async {
    final e = byId(eventId);
    if (e == null || e.cameraId != cameraId) return null;
    e.endedAt ??= _now();
    if (peakScore != null && peakScore > e.peakScore) e.peakScore = peakScore;
    await _persist();
    return e;
  }

  /// Closes events left open (e.g. the camera disconnected mid-motion).
  Future<void> closeOngoing(String cameraId) async {
    var changed = false;
    for (final e in _events.where((e) => e.cameraId == cameraId && e.isOngoing)) {
      e.endedAt = _now();
      changed = true;
    }
    if (changed) await _persist();
  }

  Future<void> markSeen(Iterable<String> ids) async {
    final set = ids.toSet();
    for (final e in _events.where((e) => set.contains(e.id))) {
      e.seen = true;
    }
    await _persist();
  }

  /// Records the AI outcome for an event: a description, or why there is none.
  Future<void> setAiResult(String id, {String? summary, String? category, String? threatLevel, String? error}) async {
    final e = byId(id);
    if (e == null) return;
    e
      ..aiSummary = summary
      ..aiCategory = category
      ..aiThreatLevel = threatLevel
      ..aiError = error;
    await _persist();
  }

  Future<void> delete(String id) async {
    final e = byId(id);
    if (e == null) return;
    _events.remove(e);
    await _deleteSnapshot(e);
    await _persist();
  }

  Future<void> clear() async {
    for (final e in List.of(_events)) {
      await _deleteSnapshot(e);
    }
    _events.clear();
    await _persist();
  }

  Future<void> _prune() async {
    final cutoff = _now().subtract(retention);
    final doomed = <CameraEvent>{
      ..._events.where((e) => e.startedAt.isBefore(cutoff)),
      if (_events.length > maxEvents) ..._events.sublist(maxEvents),
    };
    if (doomed.isEmpty) return;
    _events.removeWhere(doomed.contains);
    for (final e in doomed) {
      await _deleteSnapshot(e);
    }
  }

  Future<void> _deleteSnapshot(CameraEvent e) async {
    final f = snapshotOf(e);
    if (f != null && await f.exists()) await f.delete();
  }

  Future<void> _persist() => _enqueue(() => _writeJson(_eventsFile, _events.map((e) => e.toJson()).toList()));

  /// Writes are serialised so concurrent updates never interleave.
  Future<void> _enqueue(Future<void> Function() write) {
    final next = _writeQueue.then((_) => write());
    _writeQueue = next.catchError((_) {});
    return next;
  }

  /// Atomic write: temp file then rename, so a crash never leaves half a file.
  static Future<void> _writeJson(File file, Object data) async {
    final tmp = File('${file.path}.tmp');
    await tmp.writeAsString(jsonEncode(data), flush: true);
    await tmp.rename(file.path);
  }

  static Future<List<T>> _readList<T>(File file, T Function(Map<String, dynamic>) parse) async {
    if (!await file.exists()) return [];
    try {
      final raw = jsonDecode(await file.readAsString()) as List;
      return raw.map((e) => parse(Map<String, dynamic>.from(e as Map))).toList();
    } catch (_) {
      return [];
    }
  }
}
