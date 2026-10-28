import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smart_spectator_camera/core/ai/ai_client.dart';
import 'package:smart_spectator_camera/core/control/control_client.dart';
import 'package:smart_spectator_camera/core/motion/motion_reporter.dart';
import 'package:smart_spectator_camera/core/pairing/pairing_client.dart';
import 'package:smart_spectator_camera/hub/alert_service.dart';
import 'package:smart_spectator_camera/hub/device_registry.dart';
import 'package:smart_spectator_camera/hub/event_store.dart';
import 'package:smart_spectator_camera/hub/hub_server.dart';

final _jpeg = Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 4, 4, 4, 0xFF, 0xD9]);
final _config = AiConfig(proxyUrl: Uri.parse('http://proxy.test'), token: 't0k');

/// Fake AI proxy: answers with [body] and [status], records requests.
AiClient fakeAi(List<http.Request> seen, {int status = 200, Map<String, dynamic>? body, Duration delay = Duration.zero}) =>
    AiClient(_config, httpClient: MockClient((req) async {
      seen.add(req);
      await Future<void>.delayed(delay);
      return http.Response(
          jsonEncode(body ??
              {
                'summary': 'A person walks to the front door.',
                'category': 'person',
                'threat_level': 'none',
                'people_count': 1,
                'confidence': 0.92,
                'model': 'grok-test',
              }),
          status);
    }));

void main() {
  late Directory dir;
  late EventStore store;
  late List<(String, String)> notifications;

  Future<void> notify({required int id, required String title, required String body}) async => notifications.add((title, body));

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('ss_ai_test');
    store = EventStore(dir: dir);
    await store.load();
    notifications = [];
  });

  tearDown(() async => dir.delete(recursive: true));

  Future<CameraEvent> motion() => store.startMotion(cameraId: 'cam_a', cameraName: 'Front door', score: 0.2, snapshotJpeg: _jpeg);

  group('AiClient', () {
    test('sends the snapshot with the proxy token and parses the insight', () async {
      final seen = <http.Request>[];
      final r = await fakeAi(seen).analyze(jpeg: _jpeg, cameraId: 'cam_a', cameraName: 'Front door');
      expect(r.insight?.summary, 'A person walks to the front door.');
      expect(r.insight?.peopleCount, 1);
      expect(seen.single.url.toString(), 'http://proxy.test/v1/analyze');
      expect(seen.single.headers['Authorization'], 'Bearer t0k');
      expect(base64Decode((jsonDecode(seen.single.body) as Map)['image_jpeg_base64'] as String), _jpeg);
    });

    test('turns proxy errors into readable messages', () async {
      final r = await fakeAi([], status: 502, body: {'error': 'ai_not_authorised'}).analyze(jpeg: _jpeg, cameraId: 'c', cameraName: 'c');
      expect(r.ok, isFalse);
      expect(r.error, contains('Groq key'));
    });

    test('is a no-op when the build has no AI configured', () async {
      final r = await AiClient(const AiConfig()).analyze(jpeg: _jpeg, cameraId: 'c', cameraName: 'c');
      expect(r.error, contains('not set up'));
    });
  });

  group('AlertService', () {
    test('AI off: plain motion notification, nothing sent to the AI', () async {
      final seen = <http.Request>[];
      final alerts = AlertService(store: store, ai: fakeAi(seen), notify: notify);
      await alerts.onMotion(await motion());
      expect(seen, isEmpty, reason: 'AI is opt-in per camera');
      expect(notifications.single.$1, 'Motion · Front door');
    });

    test('AI on: the notification uses the AI description, which is saved on the event', () async {
      await store.updateSettings('cam_a', const CameraSettings(aiEnabled: true));
      final alerts = AlertService(store: store, ai: fakeAi([]), notify: notify);
      final e = await motion();
      await alerts.onMotion(e);
      expect(notifications.single, ('Front door: Person', 'A person walks to the front door.'));
      expect(store.byId(e.id)!.aiSummary, 'A person walks to the front door.');
      expect(store.byId(e.id)!.aiCategory, 'person');
    });

    test('AI says nothing happened: no notification', () async {
      await store.updateSettings('cam_a', const CameraSettings(aiEnabled: true));
      final ai = fakeAi([], body: {'summary': 'Sunlight moved across the floor.', 'category': 'no_activity', 'threat_level': 'none', 'people_count': 0, 'confidence': 0.8});
      await AlertService(store: store, ai: ai, notify: notify).onMotion(await motion());
      expect(notifications, isEmpty);
    });

    test('AI failure: still alerts, and records why there is no description', () async {
      await store.updateSettings('cam_a', const CameraSettings(aiEnabled: true));
      final ai = fakeAi([], status: 429, body: {'error': 'daily_limit_reached'});
      final e = await motion();
      await AlertService(store: store, ai: ai, notify: notify).onMotion(e);
      expect(notifications.single.$1, 'Motion · Front door');
      expect(store.byId(e.id)!.aiError, contains('limit'));
    });

    test('slow AI: alert goes out after the wait, description arrives later', () async {
      await store.updateSettings('cam_a', const CameraSettings(aiEnabled: true));
      final ai = fakeAi([], delay: const Duration(milliseconds: 300));
      final e = await motion();
      await AlertService(store: store, ai: ai, notify: notify, aiWait: const Duration(milliseconds: 50)).onMotion(e);
      expect(notifications.single.$1, 'Motion · Front door');
      await Future<void>.delayed(const Duration(milliseconds: 400));
      expect(store.byId(e.id)!.aiSummary, isNotNull);
    });

    test('at most one alert per camera per cooldown; notifications can be turned off', () async {
      final alerts = AlertService(store: store, ai: fakeAi([]), notify: notify, cooldown: const Duration(minutes: 1));
      await alerts.onMotion(await motion());
      await alerts.onMotion(await motion());
      expect(notifications.length, 1);
      await store.updateSettings('cam_b', const CameraSettings(notify: false));
      await alerts.onMotion(await store.startMotion(cameraId: 'cam_b', cameraName: 'Back', score: 0.1));
      expect(notifications.length, 1);
    });

    test('Ask AI saves an "AI check" event with the answer', () async {
      final (event, result) = await AlertService(store: store, ai: fakeAi([]), notify: notify)
          .analyzeSnapshot(cameraId: 'cam_a', cameraName: 'Front door', jpeg: _jpeg);
      expect(result.ok, isTrue);
      expect(event.type, 'ai_check');
      expect(store.byId(event.id)!.aiSummary, isNotNull);
      expect(store.byId(event.id)!.seen, isTrue);
      expect(store.snapshotOf(event)!.readAsBytesSync(), _jpeg);
    });
  });

  test('Ask AI snapshot round trip: main phone asks, only that camera can answer', () async {
    final registry = DeviceRegistry(store: InMemoryDeviceStore());
    await registry.load();
    final server = HubServer(registry: registry, port: 0, bindAddress: InternetAddress.loopbackIPv4);
    await server.start();
    final hub = HubAddress('127.0.0.1', server.boundPort!);
    final cam = await PairingClient.pairWithCode(hub: hub, deviceId: 'dev_a', deviceName: 'A', code: registry.hubCode);
    final other = await PairingClient.pairWithCode(hub: hub, deviceId: 'dev_b', deviceName: 'B', code: registry.hubCode);

    final reporter = MotionReporter(hub: hub, deviceToken: cam.deviceToken!);
    final intruder = MotionReporter(hub: hub, deviceToken: other.deviceToken!);
    final control = ControlClient(
      hubIp: '127.0.0.1',
      hubPort: hub.port,
      deviceId: 'dev_a',
      cameraId: cam.cameraId!,
      deviceToken: cam.deviceToken!,
      onCommand: (cmd) async {
        if (cmd['action'] != 'capture_snapshot') return;
        final id = cmd['request_id'] as String;
        expect(await intruder.uploadSnapshot(requestId: id, jpeg: _jpeg), isFalse);
        await reporter.uploadSnapshot(requestId: id, jpeg: _jpeg);
      },
    );
    await control.start();

    expect(await server.requestSnapshot(cam.cameraId!), _jpeg);
    expect(await server.requestSnapshot('cam_unknown'), isNull);

    control.stop();
    await server.dispose();
  });
}
