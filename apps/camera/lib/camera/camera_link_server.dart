import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import '../core/net/local_host.dart';
import '../core/pairing/code_guard.dart';
import '../core/storage/credential_store.dart';

/// A main phone asking to receive this camera's video. The camera's owner
/// answers on the camera phone; [closed] completes when the question is over
/// (answered, timed out or abandoned), so the prompt can close itself.
class LinkRequest {
  final String hubName;
  final String hubHost;
  final Completer<void> _closed = Completer<void>();

  LinkRequest({required this.hubName, required this.hubHost});

  Future<void> get closed => _closed.future;
}

/// Small LAN server on the camera phone so main phones can add this camera by
/// entering the camera's code (the reverse of entering the main phone's code).
/// One camera can be added by several main phones and streams to all of them,
/// but only after the camera's owner allows each one on the camera phone: the
/// code alone is not enough.
///
///   GET  /api/v1/camera/info          → {"role":"camera","device_id","device_name"}
///   POST /api/v1/camera/link/check    {"code"} → 200 if correct
///   POST /api/v1/camera/link/approve  {"code","hub_name"} → asks on the camera,
///                                     200 {"approval"} | 403 declined | 408 no answer
///   POST /api/v1/camera/link          {"code","approval","hub_port","hub_name","camera_id","device_token"}
///
/// The main phone's address is taken from the connection itself, not from the
/// request body, so a link always points back at the phone that made it, and
/// an approval only works for the address it was given to.
class CameraLinkServer {
  static const int defaultPort = 8100;
  static const int maxBodyBytes = 16 * 1024;

  final String deviceId;
  String deviceName;
  final CodeGuard guard;
  final Future<void> Function(HubLink link) onLinked;

  /// Asks the camera's owner whether [LinkRequest.hubName] may receive video.
  /// Returns true to allow; false, or no answer within [approvalTimeout], refuses.
  final Future<bool> Function(LinkRequest request) approve;
  final Duration approvalTimeout;

  /// After "Don't allow", the same address must wait this long to ask again.
  final Duration declineCooldown;
  final InternetAddress bindAddress;

  HttpServer? _server;
  LinkRequest? _asking;
  final Map<String, (String host, DateTime expires)> _approvals = {};
  final Map<String, DateTime> _declinedUntil = {};
  final Random _random = Random.secure();
  final DateTime Function() _now;

  CameraLinkServer({
    required this.deviceId,
    required this.deviceName,
    required this.guard,
    required this.onLinked,
    required this.approve,
    this.approvalTimeout = const Duration(seconds: 60),
    this.declineCooldown = const Duration(seconds: 30),
    InternetAddress? bindAddress,
    DateTime Function()? now,
  })  : bindAddress = bindAddress ?? InternetAddress.anyIPv4,
        _now = now ?? DateTime.now;

  int? get port => _server?.port;

  /// Binds [preferredPort], or the next free port up to +10.
  Future<int> start({int preferredPort = defaultPort}) async {
    if (_server != null) return _server!.port;
    Object? lastError;
    for (var p = preferredPort; p <= (preferredPort == 0 ? 0 : preferredPort + 10); p++) {
      try {
        _server = await HttpServer.bind(bindAddress, p);
        _server!.listen(_handle, onError: (_) {});
        return _server!.port;
      } on SocketException catch (e) {
        lastError = e;
      }
    }
    throw lastError ?? StateError('No free port');
  }

  Future<void> stop() async {
    await _server?.close(force: true);
    _server = null;
  }

  Future<void> _handle(HttpRequest req) async {
    try {
      final path = req.uri.path;
      // Only requests addressed to this phone by its address (see isLocalHost).
      if (!isLocalHost(req.headers.value(HttpHeaders.hostHeader))) {
        return await _json(req.response, 421, {'detail': 'Open VYRO by the phone\'s address.'});
      }
      if (path == '/api/v1/camera/info' && req.method == 'GET') {
        return await _json(req.response, 200, {'role': 'camera', 'device_id': deviceId, 'device_name': deviceName});
      }
      if (path == '/api/v1/camera/link/check' && req.method == 'POST') {
        final body = await _readJson(req);
        final check = guard.check(body?['code'] is String ? body!['code'] as String : '', caller: _caller(req));
        return await _json(req.response, check.ok ? 200 : (check.locked ? 423 : 400), {
          if (!check.ok) 'detail': check.message,
          if (check.ok) 'status': 'ok',
        });
      }
      if (path == '/api/v1/camera/link/approve' && req.method == 'POST') {
        return await _approve(req);
      }
      if (path == '/api/v1/camera/link' && req.method == 'POST') {
        return await _link(req);
      }
      return await _json(req.response, 404, {'detail': 'Not found'});
    } catch (_) {
      try {
        await _json(req.response, 500, {'detail': 'Internal error'});
      } catch (_) {}
    }
  }

  String _caller(HttpRequest req) => req.connectionInfo?.remoteAddress.address ?? '';

  /// Asks the camera's owner to allow the calling main phone (one question at
  /// a time). On "Allow" the caller gets a single-use approval for [_link].
  Future<void> _approve(HttpRequest req) async {
    final body = await _readJson(req);
    if (body == null) return _json(req.response, 400, {'detail': 'Invalid JSON body'});
    final host = _caller(req);
    final check = guard.check(body['code'] is String ? body['code'] as String : '', caller: host);
    if (!check.ok) return _json(req.response, check.locked ? 423 : 400, {'detail': check.message});
    final now = _now();
    final declined = _declinedUntil[host];
    if (declined != null && now.isBefore(declined)) {
      return _json(req.response, 429, {'detail': 'The camera phone did not allow this main phone. Try again in a moment.'});
    }
    if (_asking != null) {
      return _json(req.response, 409, {'detail': 'The camera phone is already answering another main phone. Try again in a moment.'});
    }
    final hubName = body['hub_name'];
    final request = LinkRequest(hubName: _cleanName(hubName), hubHost: host);
    _asking = request;
    bool? allowed;
    try {
      allowed = await approve(request).then<bool?>((ok) => ok).timeout(approvalTimeout, onTimeout: () => null);
    } catch (_) {
      allowed = false;
    } finally {
      _asking = null;
      request._closed.complete();
    }
    if (allowed == null) {
      return _json(req.response, 408, {'detail': 'Nobody answered on the camera phone. Add it again and tap Allow on the camera.'});
    }
    if (!allowed) {
      _declinedUntil[host] = _now().add(declineCooldown);
      return _json(req.response, 403, {'detail': 'The camera phone did not allow this main phone.'});
    }
    _approvals.removeWhere((_, a) => _now().isAfter(a.$2));
    final approval = List.generate(16, (_) => _random.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
    _approvals[approval] = (host, _now().add(const Duration(minutes: 2)));
    return _json(req.response, 200, {'approval': approval});
  }

  Future<void> _link(HttpRequest req) async {
    final body = await _readJson(req);
    if (body == null) return _json(req.response, 400, {'detail': 'Invalid JSON body'});
    final check = guard.check(body['code'] is String ? body['code'] as String : '', caller: _caller(req));
    if (!check.ok) return _json(req.response, check.locked ? 423 : 400, {'detail': check.message});
    // Single use, for the address it was given to, and recent.
    final approval = body['approval'] is String ? _approvals.remove(body['approval']) : null;
    if (approval == null || approval.$1 != _caller(req) || _now().isAfter(approval.$2)) {
      return _json(req.response, 403, {
        'detail': 'Allow this main phone on the camera phone first. If the camera never asks, update VYRO on the main phone.',
      });
    }

    final port = (body['hub_port'] as num?)?.toInt();
    final cameraId = body['camera_id'];
    final token = body['device_token'];
    final hubName = body['hub_name'];
    if (port == null || port < 1 || port > 65535) return _json(req.response, 422, {'detail': 'Invalid hub_port'});
    if (cameraId is! String || !RegExp(r'^[A-Za-z0-9_\-]{3,64}$').hasMatch(cameraId)) {
      return _json(req.response, 422, {'detail': 'Invalid camera_id'});
    }
    if (token is! String || !token.startsWith('ss_tok_v1_') || token.length > 128) {
      return _json(req.response, 422, {'detail': 'Invalid device_token'});
    }
    final host = req.connectionInfo?.remoteAddress.address;
    if (host == null) return _json(req.response, 400, {'detail': 'Unknown caller address'});

    await onLinked(HubLink(
      hubHost: host,
      hubPort: port,
      hubName: _cleanName(hubName),
      cameraId: cameraId,
      deviceToken: token,
    ));
    return _json(req.response, 200, {'status': 'linked', 'device_id': deviceId});
  }

  static String _cleanName(Object? name) =>
      name is String && name.trim().isNotEmpty ? name.trim().substring(0, name.trim().length.clamp(0, 64)) : 'Main phone';

  Future<Map<String, dynamic>?> _readJson(HttpRequest req) async {
    final builder = BytesBuilder(copy: false);
    await for (final chunk in req) {
      builder.add(chunk);
      if (builder.length > maxBodyBytes) return null;
    }
    try {
      final decoded = jsonDecode(utf8.decode(builder.takeBytes()));
      return decoded is Map ? Map<String, dynamic>.from(decoded) : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> _json(HttpResponse res, int status, Map<String, dynamic> body) async {
    res.statusCode = status;
    res.headers.contentType = ContentType.json;
    res.write(jsonEncode(body));
    await res.close();
  }
}
