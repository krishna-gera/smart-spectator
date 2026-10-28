import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/hub/event_store.dart';

final _jpeg = Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 1, 2, 3, 0xFF, 0xD9]);

void main() {
  late Directory dir;
  late DateTime now;

  EventStore store({int maxEvents = 500}) =>
      EventStore(dir: dir, maxEvents: maxEvents, retention: const Duration(days: 7), now: () => now);

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('ss_events_test');
    now = DateTime(2026, 10, 28, 12);
  });

  tearDown(() async => dir.delete(recursive: true));

  test('motion start and end are stored with a snapshot and survive a restart', () async {
    final s = store();
    await s.load();
    final e = await s.startMotion(cameraId: 'cam_a', cameraName: 'Camera A', score: 0.1, rotationDegrees: 90, snapshotJpeg: _jpeg);
    expect(s.snapshotOf(e)!.readAsBytesSync(), _jpeg);
    expect(s.unseenCount, 1);

    now = now.add(const Duration(seconds: 12));
    await s.endMotion(eventId: e.id, cameraId: 'cam_a', peakScore: 0.4);

    final reloaded = store();
    await reloaded.load();
    final r = reloaded.events.single;
    expect(r.cameraName, 'Camera A');
    expect(r.duration, const Duration(seconds: 12));
    expect(r.peakScore, 0.4);
    expect(r.rotationDegrees, 90);
    expect(reloaded.snapshotOf(r)!.existsSync(), isTrue);
  });

  test('a camera cannot end another camera\'s event', () async {
    final s = store();
    await s.load();
    final e = await s.startMotion(cameraId: 'cam_a', cameraName: 'A', score: 0.1);
    expect(await s.endMotion(eventId: e.id, cameraId: 'cam_b'), isNull);
    expect(s.byId(e.id)!.isOngoing, isTrue);
  });

  test('events are newest first; seen, delete and clear work and remove files', () async {
    final s = store();
    await s.load();
    final first = await s.startMotion(cameraId: 'c', cameraName: 'C', score: 0.1, snapshotJpeg: _jpeg);
    now = now.add(const Duration(minutes: 1));
    final second = await s.startMotion(cameraId: 'c', cameraName: 'C', score: 0.2, snapshotJpeg: _jpeg);
    expect(s.events.map((e) => e.id), [second.id, first.id]);

    await s.markSeen([first.id]);
    expect(s.unseenCount, 1);

    final firstFile = s.snapshotOf(first)!;
    await s.delete(first.id);
    expect(firstFile.existsSync(), isFalse);
    expect(s.events.single.id, second.id);

    final secondFile = s.snapshotOf(second)!;
    await s.clear();
    expect(s.events, isEmpty);
    expect(secondFile.existsSync(), isFalse);
  });

  test('old events and events beyond the limit are pruned with their snapshots', () async {
    final s = store(maxEvents: 2);
    await s.load();
    final old = await s.startMotion(cameraId: 'c', cameraName: 'C', score: 0.1, snapshotJpeg: _jpeg);
    final oldFile = s.snapshotOf(old)!;

    now = now.add(const Duration(days: 8));
    await s.startMotion(cameraId: 'c', cameraName: 'C', score: 0.1);
    expect(s.byId(old.id), isNull, reason: 'older than 7 days');
    expect(oldFile.existsSync(), isFalse);

    await s.startMotion(cameraId: 'c', cameraName: 'C', score: 0.1);
    await s.startMotion(cameraId: 'c', cameraName: 'C', score: 0.1);
    expect(s.events.length, 2, reason: 'capped at maxEvents');
  });

  test('closeOngoing ends events left open by a disconnected camera', () async {
    final s = store();
    await s.load();
    final e = await s.startMotion(cameraId: 'cam_a', cameraName: 'A', score: 0.1);
    await s.closeOngoing('cam_a');
    expect(s.byId(e.id)!.isOngoing, isFalse);
  });

  test('camera settings persist and default sensibly', () async {
    final s = store();
    await s.load();
    expect(s.settingsFor('cam_a').motionEnabled, isTrue);
    expect(s.settingsFor('cam_a').sensitivity, 0.5);
    await s.updateSettings('cam_a', const CameraSettings(motionEnabled: false, sensitivity: 0.8, notify: false));

    final reloaded = store();
    await reloaded.load();
    final st = reloaded.settingsFor('cam_a');
    expect((st.motionEnabled, st.sensitivity, st.notify), (false, 0.8, false));
  });

  test('a corrupt index file does not crash loading', () async {
    await File('${dir.path}/events.json').writeAsString('{not json');
    final s = store();
    await s.load();
    expect(s.events, isEmpty);
  });
}
