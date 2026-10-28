import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import '../core/ai/ai_client.dart';
import 'brand_assets.dart';
import 'camera_adder.dart';
import 'event_store.dart';
import 'hub_server.dart';
import 'watch_tasks.dart';
import 'web_dashboard.dart';

/// Browser dashboard served by the main phone at `http://<main-phone>:8000/`.
///
/// Sign-in uses the main phone's pairing code (same lockout as cameras) and
/// creates an HttpOnly, SameSite=Strict session cookie, so images and API
/// calls are authenticated without tokens in URLs. Works only while the main
/// phone app is open and on the same network.
///
///   GET    /                                   dashboard page
///   POST   /api/v1/web/login                   {"code"} → sets cookie
///   POST   /api/v1/web/logout
///   GET    /api/v1/web/state                   cameras, events, hub info
///   GET    /api/v1/web/cameras/{id}/frame      current JPEG (≈1 per second)
///   PUT    /api/v1/web/cameras/{id}/settings   partial CameraSettings JSON
///   POST   /api/v1/web/cameras/{id}/ask-ai     describe the current picture
///   GET    /api/v1/web/events/{id}/snapshot    event JPEG
///   POST   /api/v1/web/events/seen             mark all events seen
///   POST   /api/v1/web/tasks                   create an AI watch task
///   POST   /api/v1/web/tasks/{id}/{action}     pause | resume | stop | ack
///   DELETE /api/v1/web/tasks/{id}
class WebApi {
  static const cookieName = 'ss_session';
  static const sessionTtl = Duration(hours: 12);
  static const frameCacheFor = Duration(milliseconds: 800);

  /// Served without signing in (home-screen icon and manifest).
  static const publicFiles = {'/manifest.webmanifest', '/apple-touch-icon.png', '/icon-192.png', '/icon-512.png'};

  final HubServer server;
  final Map<String, DateTime> _sessions = {};
  final Map<String, (DateTime, Uint8List)> _frames = {};
  final Map<String, Future<Uint8List?>> _frameInFlight = {};
  final Random _random = Random.secure();

  /// Set by the app when AI is available ("Ask AI" in the browser).
  Future<AiResult> Function(String cameraId)? onAskAi;
  bool aiAvailable = false;

  /// AI watch tasks (set by the app once the watcher is running).
  TaskWatcher? tasks;

  /// Adds a camera by its code (tests replace the Wi-Fi search).
  Future<String> Function(String code)? addCamera;

  WebApi(this.server);

  Future<void> handle(HttpRequest req) async {
    final path = req.uri.path;
    final res = req.response;
    _securityHeaders(res);

    if (path == '/' && req.method == 'GET') {
      res.headers.contentType = ContentType.html;
      res.write(dashboardHtml);
      return res.close();
    }
    // "Add to Home Screen": VYRO name and icon.
    if (path == '/manifest.webmanifest' && req.method == 'GET') {
      res.headers.contentType = ContentType('application', 'manifest+json', charset: 'utf-8');
      res.write(jsonEncode({
        'name': 'VYRO',
        'short_name': 'VYRO',
        'description': 'Your VYRO cameras, events and AI tasks.',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#1C1E24',
        'theme_color': '#1C1E24',
        'icons': [
          {'src': '/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
          {'src': '/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
          {'src': '/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
      }));
      return res.close();
    }
    final icon = switch (path) {
      '/apple-touch-icon.png' => vyroIcon180Base64,
      '/icon-192.png' => vyroIcon192Base64,
      '/icon-512.png' => vyroIcon512Base64,
      _ => null,
    };
    if (icon != null && req.method == 'GET') {
      res.headers
        ..contentType = ContentType('image', 'png')
        ..set(HttpHeaders.cacheControlHeader, 'public, max-age=604800');
      res.add(base64Decode(icon));
      return res.close();
    }
    if (path == '/api/v1/web/login' && req.method == 'POST') return _login(req);

    if (!_authenticated(req)) return _json(res, 401, {'detail': 'Sign in with the main phone\'s pairing code.'});

    if (path == '/api/v1/web/logout' && req.method == 'POST') {
      _sessions.remove(_cookie(req));
      res.headers.add(HttpHeaders.setCookieHeader, '$cookieName=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict');
      return _json(res, 200, {'status': 'signed_out'});
    }
    if (path == '/api/v1/web/state' && req.method == 'GET') return _json(res, 200, _state());
    if (path == '/api/v1/web/events/seen' && req.method == 'POST') {
      await server.events?.markSeen(server.events!.events.map((e) => e.id));
      return _json(res, 200, {'status': 'ok'});
    }

    final parts = path.split('/'); // ['', 'api', 'v1', 'web', kind, id, action]
    if (parts.length >= 5 && parts[4] == 'tasks') return _tasks(req, parts);
    if (path == '/api/v1/web/cameras/add' && req.method == 'POST') return _addCamera(req);
    if (parts.length == 6 && parts[4] == 'cameras' && req.method == 'DELETE') return _removeCamera(res, parts[5]);
    if (parts.length == 7 && parts[4] == 'cameras') {
      final id = parts[5];
      if (!server.cameras.any((c) => c.cameraId == id)) return _json(res, 404, {'detail': 'Unknown camera'});
      switch ((parts[6], req.method)) {
        case ('frame', 'GET'):
          return _frame(res, id);
        case ('picture', 'GET'):
          return _lastPicture(res, id);
        case ('settings', 'PUT'):
          return _settings(req, id);
        case ('ask-ai', 'POST'):
          return _askAi(res, id);
        case ('rename', 'POST'):
          return _rename(req, id);
      }
    }
    if (parts.length == 7 && parts[4] == 'events' && parts[6] == 'snapshot' && req.method == 'GET') {
      final e = server.events?.byId(parts[5]);
      final file = e == null ? null : server.events!.snapshotOf(e);
      if (file == null || !await file.exists()) return _json(res, 404, {'detail': 'No snapshot'});
      res.headers
        ..contentType = ContentType('image', 'jpeg')
        ..set(HttpHeaders.cacheControlHeader, 'private, max-age=86400');
      res.add(await file.readAsBytes());
      return res.close();
    }
    return _json(res, 404, {'detail': 'Not found'});
  }

  // ---------------------------------------------------------------- auth

  Future<void> _login(HttpRequest req) async {
    Map<String, dynamic>? body;
    try {
      final raw = await utf8.decoder.bind(req).join();
      if (raw.length < 1024) body = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    } catch (_) {}
    final code = body?['code'];
    if (code is! String) return _json(req.response, 400, {'detail': 'Enter the 6-digit code.'});
    final check = server.registry.checkHubCode(code);
    if (!check.ok) return _json(req.response, check.locked ? 429 : 401, {'detail': check.message});

    final token = List.generate(32, (_) => _random.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
    _sessions[token] = DateTime.now().add(sessionTtl);
    req.response.headers.add(HttpHeaders.setCookieHeader,
        '$cookieName=$token; Path=/; Max-Age=${sessionTtl.inSeconds}; HttpOnly; SameSite=Strict');
    return _json(req.response, 200, {'status': 'signed_in'});
  }

  String? _cookie(HttpRequest req) {
    for (final c in req.cookies) {
      if (c.name == cookieName) return c.value;
    }
    return null;
  }

  bool _authenticated(HttpRequest req) {
    final token = _cookie(req);
    if (token == null) return false;
    final expires = _sessions[token];
    if (expires == null) return false;
    if (DateTime.now().isAfter(expires)) {
      _sessions.remove(token);
      return false;
    }
    return true;
  }

  // ---------------------------------------------------------------- data

  Map<String, dynamic> _state() {
    final store = server.events;
    return {
      'hub': {
        'name': server.displayName,
        'port': server.boundPort,
        'ai_available': aiAvailable,
      },
      'cameras': [
        for (final c in server.cameras)
          {
            'camera_id': c.cameraId,
            'name': c.deviceName,
            'status': _status(c),
            'battery': c.batteryLevel?.round(),
            'charging': c.isCharging,
            'battery_low': c.batteryLow,
            'last_seen': c.lastSeenAt?.toUtc().toIso8601String(),
            'picture_at': c.lastPictureAt?.toUtc().toIso8601String(),
            'picture_rotation': c.lastPictureRotation,
            'motion_active': c.motionActive,
            'rotation': c.rotationDegrees,
            'bitrate_kbps': c.bitrateKbps.round(),
            'settings': (store?.settingsFor(c.cameraId) ?? const CameraSettings()).toJson(),
          }
      ],
      'events': [
        for (final e in (store?.events ?? const <CameraEvent>[]).take(300))
          {
            'id': e.id,
            'camera_id': e.cameraId,
            'camera_name': e.cameraName,
            'type': e.type,
            'started_at': e.startedAt.toUtc().toIso8601String(),
            'ended_at': e.endedAt?.toUtc().toIso8601String(),
            'peak_score': e.peakScore,
            'rotation': e.rotationDegrees,
            'seen': e.seen,
            'has_snapshot': e.snapshotFile != null,
            'ai_summary': e.aiSummary,
            'ai_category': e.aiCategory,
            'ai_threat_level': e.aiThreatLevel,
            'ai_error': e.aiError,
          }
      ],
      'unseen': store?.unseenCount ?? 0,
      'tasks': [
        for (final t in tasks?.store.tasks ?? const <WatchTask>[])
          {
            'id': t.id,
            'camera_id': t.cameraId,
            'camera_name': t.cameraName,
            'description': t.description,
            'question': t.question,
            'status': t.status.name,
            'status_text': t.lastError ?? describeTaskStatus(t, DateTime.now()),
            'has_error': t.lastError != null,
            'observation': t.lastObservation,
            'progress': t.lastProgress,
            'progress_applicable': t.progressApplicable,
            'needs_ack': t.needsAcknowledgement,
            'interval_seconds': t.intervalSeconds,
          }
      ],
    };
  }

  Future<void> _tasks(HttpRequest req, List<String> parts) async {
    final watcher = tasks;
    final res = req.response;
    if (watcher == null || !aiAvailable) return _json(res, 503, {'detail': 'AI tasks are not available on this main phone.'});

    if (parts.length == 5 && req.method == 'POST') {
      Map<String, dynamic> body;
      try {
        body = Map<String, dynamic>.from(jsonDecode(await utf8.decoder.bind(req).join()) as Map);
      } catch (_) {
        return _json(res, 400, {'detail': 'Invalid JSON'});
      }
      final cam = server.cameras.where((c) => c.cameraId == body['camera_id']).firstOrNull;
      final text = (body['description'] as String? ?? '').trim();
      if (cam == null) return _json(res, 404, {'detail': 'Unknown camera'});
      if (text.length < 8 || text.length > 300) return _json(res, 422, {'detail': 'Describe the task in 8–300 characters.'});
      final interval = (body['interval_seconds'] as num?)?.toInt() ?? 30;
      final auto = (body['auto_stop_minutes'] as num?)?.toInt() ?? 180;
      final t = await watcher.create(
        cameraId: cam.cameraId,
        cameraName: cam.deviceName,
        description: text,
        intervalSeconds: TaskWatcher.intervals.contains(interval) ? interval : 30,
        remindUntilAck: body['remind_until_ack'] != false,
        keepWatching: body['keep_watching'] == true,
        autoStopMinutes: const [60, 180, 480].contains(auto) ? auto : 180,
      );
      return _json(res, 201, {'id': t.id});
    }

    final task = parts.length >= 6 ? watcher.store.byId(parts[5]) : null;
    if (task == null) return _json(res, 404, {'detail': 'Unknown task'});
    if (parts.length == 6 && req.method == 'DELETE') {
      await watcher.delete(task);
      return _json(res, 200, {'status': 'deleted'});
    }
    if (parts.length == 7 && req.method == 'POST') {
      switch (parts[6]) {
        case 'pause':
          await watcher.pause(task);
        case 'resume':
          await watcher.resume(task);
        case 'stop':
          await watcher.stopTask(task);
        case 'ack':
          await watcher.acknowledge(task);
        default:
          return _json(res, 404, {'detail': 'Unknown action'});
      }
      return _json(res, 200, {'status': task.status.name});
    }
    return _json(res, 404, {'detail': 'Not found'});
  }

  static String _status(CameraLink c) => c.health().name;

  /// The camera's most recent picture, kept after it stops streaming.
  Future<void> _lastPicture(HttpResponse res, String cameraId) async {
    final jpeg = server.cameras.where((c) => c.cameraId == cameraId).firstOrNull?.lastPicture;
    if (jpeg == null) return _json(res, 404, {'detail': 'No picture yet'});
    res.headers
      ..contentType = ContentType('image', 'jpeg')
      ..set(HttpHeaders.cacheControlHeader, 'no-store');
    res.add(jpeg);
    return res.close();
  }

  /// Current picture. Several browsers share one camera snapshot per ~0.8 s.
  Future<void> _frame(HttpResponse res, String cameraId) async {
    final cached = _frames[cameraId];
    Uint8List? jpeg;
    if (cached != null && DateTime.now().difference(cached.$1) < frameCacheFor) {
      jpeg = cached.$2;
    } else {
      // Note: the cleanup must not return the removed future, or whenComplete
      // would wait for this very future and never finish.
      final pending = _frameInFlight[cameraId] ??=
          server.requestSnapshot(cameraId, timeout: const Duration(seconds: 3)).whenComplete(() {
        _frameInFlight.remove(cameraId);
      });
      jpeg = await pending;
      if (jpeg != null) _frames[cameraId] = (DateTime.now(), jpeg);
    }
    if (jpeg == null) return _json(res, 503, {'detail': 'Camera is not streaming'});
    res.headers
      ..contentType = ContentType('image', 'jpeg')
      ..set(HttpHeaders.cacheControlHeader, 'no-store');
    res.add(jpeg);
    return res.close();
  }

  Future<Map<String, dynamic>?> _body(HttpRequest req) async {
    try {
      final raw = await utf8.decoder.bind(req).join();
      if (raw.length > 4096) return null;
      return Map<String, dynamic>.from(jsonDecode(raw) as Map);
    } catch (_) {
      return null;
    }
  }

  /// Adds a camera by the 6-digit code shown on the camera phone.
  Future<void> _addCamera(HttpRequest req) async {
    final body = await _body(req);
    final code = (body?['code'] as String? ?? '').trim();
    if (!RegExp(r'^\d{6}$').hasMatch(code)) return _json(req.response, 422, {'detail': 'The camera code has 6 digits.'});
    final port = server.boundPort;
    if (port == null) return _json(req.response, 503, {'detail': 'The main phone is not ready.'});
    String name;
    try {
      name = await (addCamera ??
          (c) => CameraAdder.addByCode(code: c, registry: server.registry, hubPort: port, hubName: server.displayName))(code);
    } on AddCameraError catch (e) {
      return _json(req.response, 404, {'detail': e.message});
    }
    return _json(req.response, 200, {'name': name});
  }

  Future<void> _rename(HttpRequest req, String cameraId) async {
    final name = (await _body(req))?['name'];
    if (name is! String || !await server.renameCamera(cameraId, name)) {
      return _json(req.response, 422, {'detail': 'Use a name of 1–40 characters.'});
    }
    return _json(req.response, 200, {'name': name.trim()});
  }

  Future<void> _removeCamera(HttpResponse res, String cameraId) async {
    final cam = server.cameras.where((c) => c.cameraId == cameraId).firstOrNull;
    if (cam == null) return _json(res, 404, {'detail': 'Unknown camera'});
    await server.revokeDevice(cam.deviceId);
    await tasks?.forgetCamera(cameraId);
    return _json(res, 200, {'status': 'removed'});
  }

  Future<void> _settings(HttpRequest req, String cameraId) async {
    Map<String, dynamic> body;
    try {
      body = Map<String, dynamic>.from(jsonDecode(await utf8.decoder.bind(req).join()) as Map);
    } catch (_) {
      return _json(req.response, 400, {'detail': 'Invalid JSON'});
    }
    final current = server.events?.settingsFor(cameraId) ?? const CameraSettings();
    final next = current.copyWith(
      motionEnabled: body['motion_enabled'] is bool ? body['motion_enabled'] as bool : null,
      sensitivity: body['sensitivity'] is num ? (body['sensitivity'] as num).toDouble().clamp(0.0, 1.0) : null,
      notify: body['notify'] is bool ? body['notify'] as bool : null,
      aiEnabled: body['ai_enabled'] is bool ? (body['ai_enabled'] as bool) && aiAvailable : null,
    );
    await server.updateCameraSettings(cameraId, next);
    return _json(req.response, 200, next.toJson());
  }

  Future<void> _askAi(HttpResponse res, String cameraId) async {
    final ask = onAskAi;
    if (!aiAvailable || ask == null) return _json(res, 503, {'detail': 'AI is not available on this main phone.'});
    final result = await ask(cameraId);
    final i = result.insight;
    if (i == null) return _json(res, 502, {'detail': result.error ?? 'AI request failed'});
    return _json(res, 200, {
      'summary': i.summary,
      'category': i.category,
      'threat_level': i.threatLevel,
      'people_count': i.peopleCount,
      'confidence': i.confidence,
    });
  }

  // ---------------------------------------------------------------- helpers

  static void _securityHeaders(HttpResponse res) {
    res.headers
      ..set('X-Frame-Options', 'DENY')
      ..set('X-Content-Type-Options', 'nosniff')
      ..set('Referrer-Policy', 'no-referrer')
      ..set('Content-Security-Policy',
          "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'");
  }

  static Future<void> _json(HttpResponse res, int status, Map<String, dynamic> body) async {
    res.statusCode = status;
    res.headers
      ..contentType = ContentType.json
      ..set(HttpHeaders.cacheControlHeader, 'no-store');
    res.write(jsonEncode(body));
    await res.close();
  }
}
