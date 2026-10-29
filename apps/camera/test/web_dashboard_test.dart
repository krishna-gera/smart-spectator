import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/core/ai/ai_client.dart';
import 'package:smart_spectator_camera/core/control/control_client.dart';
import 'package:smart_spectator_camera/core/motion/motion_reporter.dart';
import 'package:smart_spectator_camera/core/pairing/pairing_client.dart';
import 'package:smart_spectator_camera/hub/camera_adder.dart';
import 'package:smart_spectator_camera/hub/device_registry.dart';
import 'package:smart_spectator_camera/hub/event_store.dart';
import 'package:smart_spectator_camera/hub/hub_server.dart';
import 'package:smart_spectator_camera/hub/watch_tasks.dart';

import 'support/cameras.dart';

final _jpeg = Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 7, 7, 7, 0xFF, 0xD9]);

/// Minimal browser: keeps the session cookie between requests.
class Browser {
  final int port;
  final HttpClient _http = HttpClient();
  final List<Cookie> cookies = [];
  Browser(this.port);

  Future<(int, HttpHeaders, List<int>)> send(String method, String path, [Object? body]) async {
    final req = await _http.open(method, '127.0.0.1', port, path);
    req.cookies.addAll(cookies);
    if (body != null) {
      req.headers.contentType = ContentType.json;
      req.write(jsonEncode(body));
    }
    final res = await req.close();
    for (final c in res.cookies) {
      cookies.removeWhere((x) => x.name == c.name);
      if (c.value.isNotEmpty) cookies.add(c);
    }
    final bytes = await res.fold<List<int>>([], (a, b) => a..addAll(b));
    return (res.statusCode, res.headers, bytes);
  }

  Future<(int, dynamic)> json(String method, String path, [Object? body]) async {
    final (status, _, bytes) = await send(method, path, body);
    return (status, bytes.isEmpty ? null : jsonDecode(utf8.decode(bytes)));
  }

  void close() => _http.close(force: true);
}

void main() {
  late Directory dir;
  late DeviceRegistry registry;
  late EventStore events;
  late HubServer server;
  late Browser browser;

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('ss_web_test');
    registry = DeviceRegistry(store: InMemoryDeviceStore(), maxHubCodeFailures: 3);
    await registry.load();
    events = EventStore(dir: dir);
    await events.load();
    server = HubServer(registry: registry, port: 0, bindAddress: InternetAddress.loopbackIPv4, events: events, displayName: 'Main phone (test)');
    await server.start();
    browser = Browser(server.boundPort!);
  });

  tearDown(() async {
    browser.close();
    await server.dispose();
    await dir.delete(recursive: true);
  });

  Future<void> signIn() async {
    final (status, _) = await browser.json('POST', '/api/v1/web/login', {'code': registry.hubCode});
    expect(status, 200);
  }

  test('serves the dashboard page with security headers', () async {
    final (status, headers, body) = await browser.send('GET', '/');
    expect(status, 200);
    expect(headers.contentType?.mimeType, 'text/html');
    expect(headers.value('content-security-policy'), contains("default-src 'self'"));
    expect(headers.value('x-frame-options'), 'DENY');
    expect(utf8.decode(body), contains('VYRO'));
  });

  test('everything else needs a signed-in session', () async {
    expect((await browser.json('GET', '/api/v1/web/state')).$1, 401);
    expect((await browser.json('GET', '/api/v1/web/cameras/x/frame')).$1, 401);
  });

  test('wrong code is refused; the right code signs in with an HttpOnly cookie', () async {
    final wrong = registry.hubCode == '111111' ? '222222' : '111111';
    expect((await browser.json('POST', '/api/v1/web/login', {'code': wrong})).$1, 401);
    final (status, headers, _) = await browser.send('POST', '/api/v1/web/login', {'code': registry.hubCode});
    expect(status, 200);
    final setCookie = headers[HttpHeaders.setCookieHeader]!.join(';');
    expect(setCookie, allOf(contains('HttpOnly'), contains('SameSite=Strict')));
    expect((await browser.json('GET', '/api/v1/web/state')).$1, 200);
  });

  test('guessing the code is locked out (shared with camera pairing)', () async {
    final wrong = registry.hubCode == '111111' ? '222222' : '111111';
    for (var i = 0; i < 2; i++) {
      await browser.json('POST', '/api/v1/web/login', {'code': wrong});
    }
    expect((await browser.json('POST', '/api/v1/web/login', {'code': wrong})).$1, 429);
    expect((await browser.json('POST', '/api/v1/web/login', {'code': registry.hubCode})).$1, 429);
  });

  test('state lists cameras with settings and events with AI fields', () async {
    final cam = await addCamera(registry, 'dev_a', 'Front door');
    final e = await events.startMotion(cameraId: cam.cameraId, cameraName: 'Front door', score: 0.2, snapshotJpeg: _jpeg);
    await events.setAiResult(e.id, summary: 'A person at the door.', category: 'person', threatLevel: 'none');
    await signIn();

    final (_, state) = await browser.json('GET', '/api/v1/web/state');
    expect(state['hub']['name'], 'Main phone (test)');
    expect(state['cameras'].single['name'], 'Front door');
    expect(state['cameras'].single['status'], 'offline');
    expect((await browser.json('GET', '/api/v1/web/cameras/${cam.cameraId}/picture')).$1, 404, reason: 'no picture yet');
    expect(state['cameras'].single['settings']['motion_enabled'], isTrue);
    expect(state['events'].single['ai_summary'], 'A person at the door.');
    expect(state['unseen'], 1);

    final (status, headers, bytes) = await browser.send('GET', '/api/v1/web/events/${e.id}/snapshot');
    expect(status, 200);
    expect(headers.contentType?.mimeType, 'image/jpeg');
    expect(bytes, _jpeg);

    expect((await browser.json('POST', '/api/v1/web/events/seen')).$1, 200);
    expect(events.unseenCount, 0);
  });

  test('settings change from the browser; AI cannot be enabled when unavailable', () async {
    final cam = await addCamera(registry, 'dev_a', 'A');
    await signIn();
    final path = '/api/v1/web/cameras/${cam.cameraId}/settings';
    final (status, body) = await browser.json('PUT', path, {'motion_enabled': false, 'sensitivity': 0.9, 'ai_enabled': true});
    expect(status, 200);
    expect(body['motion_enabled'], isFalse);
    expect(events.settingsFor(cam.cameraId).sensitivity, 0.9);
    expect(events.settingsFor(cam.cameraId).aiEnabled, isFalse);

    server.web.aiAvailable = true;
    await browser.json('PUT', path, {'ai_enabled': true});
    expect(events.settingsFor(cam.cameraId).aiEnabled, isTrue);
    expect((await browser.json('PUT', '/api/v1/web/cameras/cam_nope/settings', {})).$1, 404);
  });

  test('live picture comes from the camera; Ask AI uses the app callback', () async {
    final hub = HubAddress('127.0.0.1', server.boundPort!);
    final cam = await addCamera(registry, 'dev_a', 'A');
    final reporter = MotionReporter(hub: hub, deviceToken: cam.deviceToken);
    final control = ControlClient(
      hubIp: '127.0.0.1',
      hubPort: hub.port,
      deviceId: 'dev_a',
      cameraId: cam.cameraId,
      deviceToken: cam.deviceToken,
      onCommand: (cmd) {
        if (cmd['action'] == 'capture_snapshot') reporter.uploadSnapshot(requestId: cmd['request_id'] as String, jpeg: _jpeg);
      },
    );
    await control.start();
    await signIn();

    final (status, headers, bytes) = await browser.send('GET', '/api/v1/web/cameras/${cam.cameraId}/frame');
    expect(status, 200);
    expect(headers.contentType?.mimeType, 'image/jpeg');
    expect(bytes, _jpeg);

    // The picture is kept for the dashboard after the camera stops streaming.
    final (pStatus, _, pBytes) = await browser.send('GET', '/api/v1/web/cameras/${cam.cameraId}/picture');
    expect(pStatus, 200);
    expect(pBytes, _jpeg);
    final (_, state) = await browser.json('GET', '/api/v1/web/state');
    expect(state['cameras'].single['status'], 'online');
    expect(state['cameras'].single['last_seen'], isNotNull);
    expect(state['cameras'].single['picture_at'], isNotNull);

    expect((await browser.json('POST', '/api/v1/web/cameras/${cam.cameraId}/ask-ai')).$1, 503, reason: 'AI not available yet');
    server.web
      ..aiAvailable = true
      ..onAskAi = (id) async => const AiResult.ok(
          AiInsight(summary: 'Empty hallway.', category: 'no_activity', threatLevel: 'none', peopleCount: 0, confidence: 0.9));
    final (aiStatus, ai) = await browser.json('POST', '/api/v1/web/cameras/${cam.cameraId}/ask-ai');
    expect(aiStatus, 200);
    expect(ai['summary'], 'Empty hallway.');
    control.stop();
  });

  test('home-screen icon and manifest are served without signing in', () async {
    final (mStatus, mHeaders, mBody) = await browser.send('GET', '/manifest.webmanifest');
    expect(mStatus, 200);
    expect(jsonDecode(utf8.decode(mBody))['name'], 'VYRO');
    final (iStatus, iHeaders, iBody) = await browser.send('GET', '/apple-touch-icon.png');
    expect((iStatus, iHeaders.contentType?.mimeType), (200, 'image/png'));
    expect(iBody.sublist(1, 4), utf8.encode('PNG'));
    final (_, _, page) = await browser.send('GET', '/');
    expect(utf8.decode(page), contains('apple-touch-icon'));
  });

  test('cameras: add by code, rename and remove from the browser', () async {
    final cam = await addCamera(registry, 'dev_a', 'iPhone');
    final codes = <String>[];
    server.web.addCamera = (code) async {
      codes.add(code);
      if (code != '482913') throw const AddCameraError('No camera accepted that code.');
      return 'Garage';
    };
    await signIn();

    expect((await browser.json('POST', '/api/v1/web/cameras/add', {'code': '12'})).$1, 422);
    final (badStatus, bad) = await browser.json('POST', '/api/v1/web/cameras/add', {'code': '000000'});
    expect((badStatus, bad['detail']), (404, 'No camera accepted that code.'));
    final (okStatus, ok) = await browser.json('POST', '/api/v1/web/cameras/add', {'code': '482913'});
    expect((okStatus, ok['name']), (200, 'Garage'));
    expect(codes, ['000000', '482913']);

    final path = '/api/v1/web/cameras/${cam.cameraId}';
    expect((await browser.json('POST', '$path/rename', {'name': '  Front door '})).$1, 200);
    expect(server.cameras.single.deviceName, 'Front door');
    expect((await browser.json('POST', '$path/rename', {'name': ''})).$1, 422);

    expect((await browser.json('DELETE', path)).$1, 200);
    expect(server.cameras, isEmpty);
    expect((await browser.json('DELETE', path)).$1, 404);
  });

  test('oversized requests are refused without being read in full', () async {
    Future<int> raw(String path, int size, {bool declareLength = true}) async {
      final client = HttpClient();
      final req = await client.post('127.0.0.1', server.boundPort!, path);
      req.headers.contentType = ContentType.json;
      final body = utf8.encode('{"code":"${'1' * size}"}');
      if (declareLength) req.contentLength = body.length; // otherwise sent chunked, size unknown upfront
      req.add(body);
      final status = (await req.close()).statusCode;
      client.close(force: true);
      return status;
    }

    expect(await raw('/api/v1/web/login', 200 * 1024), 413, reason: 'declared size over the sign-in limit');
    expect(await raw('/api/v1/web/login', 200 * 1024, declareLength: false), 413, reason: 'streamed body is cut off at the limit');
    expect(registry.hubCodeLockedFor, isNull, reason: 'refused before any code check');
    await signIn(); // normal-sized requests still work

    final cam = await addCamera(registry, 'dev_a', 'A');
    final client = HttpClient();
    final put = await client.put('127.0.0.1', server.boundPort!, '/api/v1/web/cameras/${cam.cameraId}/settings');
    put.cookies.addAll(browser.cookies);
    put.headers.contentType = ContentType.json;
    put.add(utf8.encode('{"motion_enabled":true,"pad":"${'x' * (64 * 1024)}"}'));
    expect((await put.close()).statusCode, 413);
    client.close(force: true);
    expect((await browser.json('PUT', '/api/v1/web/cameras/${cam.cameraId}/settings', {'sensitivity': 0.3})).$1, 200);
  });

  test('only this dashboard page can sign in or change things', () async {
    final port = server.boundPort!;
    Future<int> post(String path, String body, {String type = 'application/json', String? origin, String? host, List<Cookie> cookies = const []}) async {
      final client = HttpClient();
      final req = await client.post('127.0.0.1', port, path);
      req.cookies.addAll(cookies);
      req.headers.set(HttpHeaders.contentTypeHeader, type);
      if (origin != null) req.headers.set('origin', origin);
      if (host != null) req.headers.set(HttpHeaders.hostHeader, host);
      req.write(body);
      final status = (await req.close()).statusCode;
      client.close(force: true);
      return status;
    }

    final right = jsonEncode({'code': registry.hubCode});
    final wrong = jsonEncode({'code': registry.hubCode == '111111' ? '222222' : '111111'});
    // Another website, a form-style body, or another domain name pointed at the phone.
    expect(await post('/api/v1/web/login', wrong, origin: 'https://evil.example'), 403);
    expect(await post('/api/v1/web/login', wrong, origin: 'null'), 403);
    expect(await post('/api/v1/web/login', wrong, type: 'text/plain'), 415);
    expect(await post('/api/v1/web/login', wrong, host: 'rebind.example.com'), 421);
    for (var i = 0; i < 5; i++) {
      await post('/api/v1/web/login', wrong, origin: 'https://evil.example');
    }
    expect(registry.checkHubCode(registry.hubCode, caller: '127.0.0.1').ok, isTrue,
        reason: 'refused requests are never counted as guesses, so they cannot lock anyone out');

    // The dashboard page itself (its own origin) works.
    expect(await post('/api/v1/web/login', right, origin: 'http://127.0.0.1:$port'), 200);
    final (page, _, _) = await browser.send('GET', '/');
    expect(page, 200);

    // Signed in, changes still need the page's own origin.
    await signIn();
    final cam = await addCamera(registry, 'dev_a', 'A');
    final rename = jsonEncode({'name': 'Hacked'});
    expect(await post('/api/v1/web/cameras/${cam.cameraId}/rename', rename, origin: 'https://evil.example', cookies: browser.cookies), 403);
    expect(server.cameras.single.deviceName, 'A');
  });

  test('changing the dashboard code signs out every browser', () async {
    await signIn();
    final other = Browser(server.boundPort!);
    expect((await other.json('POST', '/api/v1/web/login', {'code': registry.hubCode})).$1, 200);
    final old = registry.hubCode;

    final fresh = await server.changeDashboardCode();
    expect(fresh, isNot(old));
    expect((await browser.json('GET', '/api/v1/web/state')).$1, 401);
    expect((await other.json('GET', '/api/v1/web/state')).$1, 401);
    expect((await browser.json('POST', '/api/v1/web/login', {'code': old})).$1, 401);
    expect((await browser.json('POST', '/api/v1/web/login', {'code': fresh})).$1, 200);
    expect((await browser.json('GET', '/api/v1/web/state')).$1, 200);
    other.close();
  });

  test('sign out ends the session', () async {
    await signIn();
    expect((await browser.json('POST', '/api/v1/web/logout')).$1, 200);
    expect((await browser.json('GET', '/api/v1/web/state')).$1, 401);
  });

  test('AI tasks: create, list, act on and delete from the browser', () async {
    final cam = await addCamera(registry, 'dev_a', 'Laundry');
    final taskStore = TaskStore(dir);
    final watcher = TaskWatcher(
      store: taskStore,
      events: events,
      ai: AiClient(AiConfig(proxyUrl: Uri.parse('http://127.0.0.1:1'), token: 't')),
      snapshot: (_) async => null,
      notify: ({required id, required title, required body}) async {},
      onWatchChanged: server.setAiWatch,
    );
    await signIn();

    expect((await browser.json('POST', '/api/v1/web/tasks', {'camera_id': cam.cameraId, 'description': 'water at max'})).$1, 503,
        reason: 'AI not available yet');
    server.web
      ..aiAvailable = true
      ..tasks = watcher;

    expect((await browser.json('POST', '/api/v1/web/tasks', {'camera_id': cam.cameraId, 'description': 'short'})).$1, 422);
    expect((await browser.json('POST', '/api/v1/web/tasks', {'camera_id': 'cam_x', 'description': 'water at max level'})).$1, 404);
    final (status, created) = await browser.json('POST', '/api/v1/web/tasks',
        {'camera_id': cam.cameraId, 'description': 'Tell me when the water reaches MAX', 'interval_seconds': 60, 'remind_until_ack': false});
    expect(status, 201);
    final t = taskStore.byId(created['id'] as String)!;
    expect((t.intervalSeconds, t.remindUntilAck, t.cameraName), (60, false, 'Laundry'));

    final (_, state) = await browser.json('GET', '/api/v1/web/state');
    expect(state['tasks'].single['description'], 'Tell me when the water reaches MAX');
    expect(state['tasks'].single['status'], 'watching');

    expect((await browser.json('POST', '/api/v1/web/tasks/${t.id}/pause')).$1, 200);
    expect(t.status, TaskStatus.paused);
    expect((await browser.json('POST', '/api/v1/web/tasks/${t.id}/resume')).$1, 200);
    expect(t.status, TaskStatus.watching);
    expect((await browser.json('POST', '/api/v1/web/tasks/${t.id}/explode')).$1, 404);
    expect((await browser.json('DELETE', '/api/v1/web/tasks/${t.id}')).$1, 200);
    expect(taskStore.tasks, isEmpty);
    watcher.dispose();
  });
}
