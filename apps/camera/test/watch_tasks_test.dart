import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smart_spectator_camera/core/ai/ai_client.dart';
import 'package:smart_spectator_camera/hub/event_store.dart';
import 'package:smart_spectator_camera/hub/hub_server.dart';
import 'package:smart_spectator_camera/hub/watch_tasks.dart';

final _jpeg = Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 5, 5, 5, 0xFF, 0xD9]);

Uint8List grid(int brightness, {int changedBlocks = 0}) {
  final g = Uint8List(32 * 18)..fillRange(0, 32 * 18, brightness);
  for (var i = 0; i < changedBlocks; i++) {
    g[i] = (brightness + 120) % 256;
  }
  return g;
}

/// Fake AI proxy: scripted plan/check answers, records calls.
class FakeAi {
  final calls = <String>[];
  final checks = <Map<String, dynamic>>[];
  Map<String, dynamic> plan = {
    'question': 'Is the water at or above the MAX line?',
    'target_visible': true,
    'advice': '',
    'progress_applicable': true,
    'current_state': 'The drum is half full.',
  };
  int status = 200;
  String? errorCode;

  AiClient client() => AiClient(AiConfig(proxyUrl: Uri.parse('http://proxy.test'), token: 't'), httpClient: MockClient((req) async {
        calls.add(req.url.path);
        if (status != 200) return http.Response(jsonEncode({'error': errorCode}), status);
        if (req.url.path == '/v1/plan-task') return http.Response(jsonEncode(plan), 200);
        return http.Response(jsonEncode(checks.isEmpty ? _check(false) : checks.removeAt(0)), 200);
      }));
}

Map<String, dynamic> _check(bool met, {double confidence = 0.9, int? progress, String obs = 'obs'}) =>
    {'condition_met': met, 'confidence': confidence, 'progress_percent': progress, 'observation': obs, 'target_visible': true};

void main() {
  late Directory dir;
  late EventStore events;
  late TaskStore store;
  late FakeAi ai;
  late DateTime now;
  late List<(String, String)> notifications;
  late Map<String, List<String>> badges;
  CameraSnapshot? nextSnapshot;

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('ss_tasks_test');
    events = EventStore(dir: dir);
    await events.load();
    store = TaskStore(dir);
    await store.load();
    ai = FakeAi();
    now = DateTime(2026, 10, 28, 15);
    notifications = [];
    badges = {};
    nextSnapshot = CameraSnapshot(_jpeg, grid(100));
  });

  tearDown(() async => dir.delete(recursive: true));

  TaskWatcher watcher() => TaskWatcher(
        store: store,
        events: events,
        ai: ai.client(),
        snapshot: (_) async => nextSnapshot,
        notify: ({required id, required title, required body}) async => notifications.add((title, body)),
        onWatchChanged: (cam, tasks) => badges[cam] = tasks,
        now: () => now,
      );

  Future<void> advance(TaskWatcher w, int seconds) async {
    now = now.add(Duration(seconds: seconds));
    await w.tick();
  }

  test('first check plans the task, later checks confirm twice before alerting', () async {
    final w = watcher();
    final t = await w.create(cameraId: 'cam_wm', cameraName: 'Laundry', description: 'Tell me when the water reaches MAX');
    expect(badges['cam_wm'], ['Tell me when the water reaches MAX'], reason: 'camera shows the AI-watching badge');

    await w.tick(); // plan
    expect(ai.calls, ['/v1/plan-task']);
    expect(t.question, 'Is the water at or above the MAX line?');
    expect(t.lastObservation, 'The drum is half full.');

    ai.checks.addAll([_check(false, progress: 70, obs: 'About 70% full.'), _check(true, progress: 100, obs: 'At MAX.'), _check(true, progress: 100, obs: 'At MAX.')]);
    nextSnapshot = CameraSnapshot(_jpeg, grid(100, changedBlocks: 40));
    await advance(w, 30);
    expect(t.lastProgress, 70);
    nextSnapshot = CameraSnapshot(_jpeg, grid(100, changedBlocks: 80));
    await advance(w, 30);
    expect(notifications, isEmpty, reason: 'one "yes" is not enough');
    await advance(w, 30);

    expect(t.status, TaskStatus.done);
    expect(notifications.single.$1, '✅ Laundry: done');
    expect(notifications.single.$2, contains('At MAX.'));
    final e = events.byId(t.doneEventId!)!;
    expect(e.type, 'task_done');
    expect(events.snapshotOf(e)!.readAsBytesSync(), _jpeg);
    expect(badges['cam_wm'], isEmpty, reason: 'badge cleared when the task finishes');
  });

  test('checks respect the interval', () async {
    final w = watcher();
    await w.create(cameraId: 'c', cameraName: 'C', description: 'd', intervalSeconds: 60, plan: const TaskPlan(question: 'q?', targetVisible: true));
    await w.tick();
    nextSnapshot = CameraSnapshot(_jpeg, grid(100, changedBlocks: 60)); // scene changes, so only the interval holds checks back
    await advance(w, 30);
    await advance(w, 29);
    expect(ai.calls.length, 1);
    await advance(w, 1);
    expect(ai.calls.length, 2);
  });

  test('an unchanged scene skips the AI call', () async {
    final w = watcher();
    final t = await w.create(cameraId: 'c', cameraName: 'C', description: 'd', plan: const TaskPlan(question: 'q?', targetVisible: true));
    await w.tick();
    expect(ai.calls.length, 1);
    await advance(w, 30); // same grid
    await advance(w, 30);
    expect(ai.calls.length, 1);
    expect(t.skippedChecks, 2);
    nextSnapshot = CameraSnapshot(_jpeg, grid(100, changedBlocks: 30));
    await advance(w, 30);
    expect(ai.calls.length, 2);
  });

  test('low-confidence "yes" does not count', () async {
    final w = watcher();
    final t = await w.create(cameraId: 'c', cameraName: 'C', description: 'd', plan: const TaskPlan(question: 'q?', targetVisible: true));
    ai.checks.addAll([_check(true, confidence: 0.4), _check(true, confidence: 0.4), _check(true, confidence: 0.4)]);
    for (var i = 0; i < 3; i++) {
      nextSnapshot = CameraSnapshot(_jpeg, grid(100, changedBlocks: 20 + i * 20));
      await advance(w, 30);
    }
    expect(t.status, TaskStatus.watching);
    expect(notifications, isEmpty);
  });

  test('reminders repeat every 2 minutes until handled', () async {
    final w = watcher();
    final t = await w.create(cameraId: 'c', cameraName: 'Tap', description: 'water', plan: const TaskPlan(question: 'q?', targetVisible: true));
    ai.checks.addAll([_check(true), _check(true)]);
    await w.tick();
    nextSnapshot = CameraSnapshot(_jpeg, grid(100, changedBlocks: 50));
    await advance(w, 30);
    expect(t.status, TaskStatus.done);
    await advance(w, 60);
    expect(notifications.length, 1);
    await advance(w, 60);
    expect(notifications.length, 2);
    expect(notifications.last.$1, '🔔 Reminder · Tap');
    await w.acknowledge(t);
    await advance(w, 300);
    expect(notifications.length, 2);
  });

  test('keep watching: alerts again only after the condition clears', () async {
    final w = watcher();
    final t = await w.create(cameraId: 'c', cameraName: 'C', description: 'd', keepWatching: true, remindUntilAck: false,
        plan: const TaskPlan(question: 'q?', targetVisible: true));
    ai.checks.addAll([_check(true), _check(true), _check(true), _check(true), _check(false), _check(true), _check(true)]);
    for (var i = 0; i < 7; i++) {
      nextSnapshot = CameraSnapshot(_jpeg, grid(100, changedBlocks: 10 + i * 30 % 500));
      await advance(w, 30);
    }
    expect(t.status, TaskStatus.watching);
    expect(notifications.length, 2);
  });

  test('auto-stops after the time limit', () async {
    final w = watcher();
    final t = await w.create(cameraId: 'c', cameraName: 'C', description: 'kettle', autoStopMinutes: 180,
        plan: const TaskPlan(question: 'q?', targetVisible: true));
    now = now.add(const Duration(hours: 3, seconds: 1));
    await w.tick();
    expect(t.status, TaskStatus.expired);
    expect(notifications.single.$1, 'Stopped watching · C');
  });

  test('busy AI: waits before retrying; camera offline is reported', () async {
    final w = watcher();
    final t = await w.create(cameraId: 'c', cameraName: 'C', description: 'd', intervalSeconds: 15, plan: const TaskPlan(question: 'q?', targetVisible: true));
    ai
      ..status = 502
      ..errorCode = 'ai_rate_limited';
    await w.tick();
    expect(t.lastError, contains('busy'));
    await advance(w, 15);
    expect(ai.calls.length, 1, reason: 'held back for the retry delay');
    await advance(w, 15);
    expect(ai.calls.length, 2);

    ai.status = 200;
    nextSnapshot = null;
    await advance(w, 30); // past the retry delay
    expect(t.lastError, contains('camera'));
  });

  test('pause, resume, delete, and persistence across restarts', () async {
    final w = watcher();
    final t = await w.create(cameraId: 'c', cameraName: 'C', description: 'printer finished');
    await w.pause(t);
    expect(badges['c'], isEmpty);
    await w.resume(t);
    expect(badges['c'], ['printer finished']);

    final reloaded = TaskStore(dir);
    await reloaded.load();
    expect(reloaded.tasks.single.description, 'printer finished');
    expect(reloaded.tasks.single.status, TaskStatus.watching);

    await w.delete(t);
    expect(store.tasks, isEmpty);
  });

  test('status line', () {
    final t = WatchTask(id: 'x', cameraId: 'c', cameraName: 'C', description: 'd', createdAt: now, startedAt: now)
      ..question = 'q'
      ..lastAiCheckAt = now.subtract(const Duration(seconds: 20));
    expect(describeTaskStatus(t, now), 'Watching · AI checked 20s ago');
  });
}
