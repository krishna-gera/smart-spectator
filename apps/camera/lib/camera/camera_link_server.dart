import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import '../core/pairing/code_guard.dart';
import '../core/storage/credential_store.dart';

/// Small LAN server on the camera phone so main phones can add this camera by
/// entering the camera's code (the reverse of entering the main phone's code).
/// One camera can be added by several main phones and streams to all of them.
///
///   GET  /api/v1/camera/info        → {"role":"camera","device_id","device_name"}
///   POST /api/v1/camera/link/check  {"code"} → 200 if correct
///   POST /api/v1/camera/link        {"code","hub_port","hub_name","camera_id","device_token"}
///
/// The main phone's address is taken from the connection itself, not from the
/// request body, so a link always points back at the phone that made it.
class CameraLinkServer {
  static const int defaultPort = 8100;
  static const int maxBodyBytes = 16 * 1024;

  final String deviceId;
  String deviceName;
  final CodeGuard guard;
  final Future<void> Function(HubLink link) onLinked;
  final InternetAddress bindAddress;

  HttpServer? _server;

  CameraLinkServer({
    required this.deviceId,
    required this.deviceName,
    required this.guard,
    required this.onLinked,
    InternetAddress? bindAddress,
  }) : bindAddress = bindAddress ?? InternetAddress.anyIPv4;

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
      if (path == '/api/v1/camera/info' && req.method == 'GET') {
        return await _json(req.response, 200, {'role': 'camera', 'device_id': deviceId, 'device_name': deviceName});
      }
      if (path == '/api/v1/camera/link/check' && req.method == 'POST') {
        final body = await _readJson(req);
        final check = guard.check(body?['code'] is String ? body!['code'] as String : '');
        return await _json(req.response, check.ok ? 200 : (check.locked ? 423 : 400), {
          if (!check.ok) 'detail': check.message,
          if (check.ok) 'status': 'ok',
        });
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

  Future<void> _link(HttpRequest req) async {
    final body = await _readJson(req);
    if (body == null) return _json(req.response, 400, {'detail': 'Invalid JSON body'});
    final check = guard.check(body['code'] is String ? body['code'] as String : '');
    if (!check.ok) return _json(req.response, check.locked ? 423 : 400, {'detail': check.message});

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
      hubName: hubName is String && hubName.isNotEmpty ? hubName.substring(0, hubName.length.clamp(0, 64)) : 'Main phone',
      cameraId: cameraId,
      deviceToken: token,
    ));
    return _json(req.response, 200, {'status': 'linked', 'device_id': deviceId});
  }

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
