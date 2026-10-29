import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import '../core/protocol/packet_decoder.dart';
import 'device_registry.dart';
import 'event_store.dart';
import 'web_api.dart';

/// How a camera looks from the main phone right now.
enum CameraHealth {
  /// Video packets arrived in the last few seconds.
  live,

  /// The video socket is open but no picture yet.
  connecting,

  /// Control channel up (battery, settings) but not streaming.
  online,

  /// Lost the connection recently; the camera usually comes back by itself.
  reconnecting,

  /// Not connected.
  offline,
}

/// Live state of one camera phone as seen by the main phone.
class CameraLink {
  /// After this long without a connection a camera counts as offline.
  static const reconnectGrace = Duration(seconds: 60);

  final String cameraId;
  final String deviceId;
  String deviceName;

  bool controlConnected = false;
  bool streaming = false;
  int packetsReceived = 0;
  int bytesReceived = 0;
  int keyframes = 0;
  int protocolErrors = 0;
  int droppedPackets = 0;
  double fps = 0;
  double bitrateKbps = 0;
  DateTime? lastPacketAt;
  double? batteryLevel;
  bool? isCharging;
  double? cameraFps;

  /// Clockwise rotation needed to show the camera's picture upright.
  int rotationDegrees = 0;

  /// Last time anything arrived from this camera (telemetry or video).
  DateTime? lastSeenAt;

  /// When the control channel dropped, and whether video was flowing then.
  DateTime? disconnectedAt;
  bool droppedWhileStreaming = false;

  /// Most recent JPEG from the camera (kept for the card and the dashboard
  /// after the camera stops streaming), with its time and rotation.
  Uint8List? lastPicture;
  DateTime? lastPictureAt;
  int lastPictureRotation = 0;

  /// Motion currently reported by this camera, and the event it belongs to.
  bool motionActive = false;
  String? activeEventId;

  int? _lastSequence;
  DateTime _windowStart = DateTime.now();
  int _windowPackets = 0;
  int _windowBytes = 0;

  CameraLink({required this.cameraId, required this.deviceId, required this.deviceName});

  CameraHealth health([DateTime? at]) {
    final now = at ?? DateTime.now();
    final last = lastPacketAt;
    if (streaming && last != null && now.difference(last).inSeconds < 3) return CameraHealth.live;
    if (streaming) return CameraHealth.connecting;
    if (controlConnected) return CameraHealth.online;
    final dropped = disconnectedAt;
    if (dropped != null && now.difference(dropped) < reconnectGrace) return CameraHealth.reconnecting;
    return CameraHealth.offline;
  }

  bool get batteryLow => batteryLevel != null && batteryLevel! <= 15 && isCharging != true;

  void _recordPacket(PacketHeader h, int wireBytes) {
    final now = DateTime.now();
    packetsReceived++;
    bytesReceived += wireBytes;
    if (h.isKeyframe) keyframes++;
    final last = _lastSequence;
    if (last != null && h.sequenceNumber > last + 1) {
      droppedPackets += h.sequenceNumber - last - 1;
    }
    _lastSequence = h.sequenceNumber;
    lastPacketAt = now;
    lastSeenAt = now;

    _windowPackets++;
    _windowBytes += wireBytes;
    final elapsedMs = now.difference(_windowStart).inMilliseconds;
    if (elapsedMs >= 1000) {
      fps = _windowPackets * 1000 / elapsedMs;
      bitrateKbps = _windowBytes * 8 / elapsedMs;
      _windowStart = now;
      _windowPackets = 0;
      _windowBytes = 0;
    }
  }

  void _resetStream() {
    streaming = false;
    fps = 0;
    bitrateKbps = 0;
    _lastSequence = null;
  }
}

/// A JPEG from a camera plus its 32x18 brightness fingerprint (when sent).
class CameraSnapshot {
  final Uint8List jpeg;
  final Uint8List? grid;
  const CameraSnapshot(this.jpeg, this.grid);
}

/// A validated video packet tagged with the camera it came from.
class CameraPacket {
  final String cameraId;
  final DecodedPacket packet;
  const CameraPacket(this.cameraId, this.packet);
}

/// Embedded LAN server that turns the main phone into the local hub.
///
/// Endpoints. Cameras are added only by their own code (CameraAdder calls the
/// camera, which then connects here with the token it was given):
///   GET  /api/v1/health
///   GET  /api/v1/devices/me                       (token check)
///   POST /api/v1/events/motion, /api/v1/snapshots (token)
///   WS   /api/v1/control/ws?token=...
///   WS   /api/v1/streams/ingest/{camera_id}?token=...
class HubServer {
  static const int defaultPort = 8000;
  static const int maxJsonBodyBytes = 16 * 1024;

  /// Motion reports carry a JPEG snapshot (base64), so they may be larger.
  static const int maxEventBodyBytes = 4 * 1024 * 1024;

  /// Event history; when null, motion reports are acknowledged but not stored.
  EventStore? events;

  /// Called when a camera reports new motion (after the event is stored).
  void Function(CameraEvent event, CameraLink camera)? onMotionStarted;

  final Map<String, (String cameraId, Completer<CameraSnapshot?>)> _snapshotRequests = {};

  /// Watch-task labels per camera; cameras show an "AI watching" badge.
  final Map<String, List<String>> _aiWatch = {};

  /// Browser dashboard served by this main phone (Phase 5).
  late final WebApi web = WebApi(this);
  int _snapshotSeq = 0;

  final DeviceRegistry registry;
  final int port;

  /// Name camera phones show in their "nearby main phones" list.
  String displayName;
  final InternetAddress bindAddress;

  HttpServer? _server;
  final Map<String, CameraLink> _links = {};
  final Map<String, WebSocket> _controlSockets = {};
  final Map<String, WebSocket> _ingestSockets = {};
  final _changes = StreamController<void>.broadcast();
  final _packets = StreamController<CameraPacket>.broadcast();

  HubServer({
    required this.registry,
    this.port = defaultPort,
    this.displayName = 'VYRO main phone',
    this.events,
    InternetAddress? bindAddress,
  }) : bindAddress = bindAddress ?? InternetAddress.anyIPv4;

  /// Fires whenever pairing, connection or stream state changes.
  Stream<void> get changes => _changes.stream;

  /// Every valid video packet; the live-view decoder subscribes here.
  Stream<CameraPacket> get packets => _packets.stream;

  bool get isRunning => _server != null;
  int? get boundPort => _server?.port;

  /// Links for every paired, non-revoked camera (connected or not).
  List<CameraLink> get cameras =>
      registry.devices.where((d) => !d.revoked).map(_linkFor).toList();

  Future<void> start() async {
    if (_server != null) return;
    _server = await HttpServer.bind(bindAddress, port, shared: true);
    _server!.listen(_handle, onError: (_) {});
    _notify();
  }

  /// iOS can close the listening socket while the app is in the background.
  /// Called on resume: restarts the server if it no longer answers.
  Future<void> ensureListening() async {
    final p = boundPort;
    if (p == null) return;
    try {
      final client = HttpClient()..connectionTimeout = const Duration(seconds: 1);
      final req = await client.get('127.0.0.1', p, '/api/v1/health');
      final res = await req.close().timeout(const Duration(seconds: 1));
      await res.drain<void>();
      client.close(force: true);
      if (res.statusCode == 200) return;
    } catch (_) {}
    await stop();
    await start();
  }

  Future<void> stop() async {
    for (final ws in [..._controlSockets.values, ..._ingestSockets.values]) {
      await ws.close(WebSocketStatus.goingAway);
    }
    _controlSockets.clear();
    _ingestSockets.clear();
    for (final l in _links.values) {
      l.controlConnected = false;
      l._resetStream();
    }
    await _server?.close(force: true);
    _server = null;
    _notify();
  }

  Future<void> dispose() async {
    await stop();
    await _changes.close();
    await _packets.close();
  }

  /// Sends a JSON command (e.g. request_idr) to a camera's control socket.
  bool sendCommand(String deviceId, Map<String, dynamic> command) {
    final ws = _controlSockets[deviceId];
    if (ws == null) return false;
    ws.add(jsonEncode(command));
    return true;
  }

  bool requestKeyframe(String cameraId) {
    final link = _links[cameraId];
    if (link == null) return false;
    return sendCommand(link.deviceId, {
      'protocol': 'ss_control_v1',
      'type': 'device_control_command',
      'target_camera_id': cameraId,
      'action': 'request_idr',
    });
  }

  Future<bool> revokeDevice(String deviceId) async {
    final ok = await registry.revoke(deviceId);
    if (!ok) return false;
    await _controlSockets.remove(deviceId)?.close(WebSocketStatus.policyViolation, 'revoked');
    final link = _links.values.where((l) => l.deviceId == deviceId).firstOrNull;
    if (link != null) {
      await _ingestSockets.remove(link.cameraId)?.close(WebSocketStatus.policyViolation, 'revoked');
      _links.remove(link.cameraId);
    }
    _notify();
    return true;
  }

  // ---------------------------------------------------------------- routing

  Future<void> _handle(HttpRequest req) async {
    final path = req.uri.path;
    try {
      if (path == '/' || path.startsWith('/api/v1/web/') || WebApi.publicFiles.contains(path)) {
        return await web.handle(req);
      }
      if (path == '/api/v1/health' && req.method == 'GET') {
        return await _json(req.response, 200, {
          'status': 'ok',
          'role': 'main_phone',
          'protocol': 'ss_v1',
          'name': displayName,
          'pairing': ['camera_code'],
        });
      }
      // A camera checks its token here to find this main phone again after
      // the main phone's Wi-Fi address changed.
      if (path == '/api/v1/devices/me' && req.method == 'GET') {
        final device = registry.authenticate(_token(req));
        if (device == null) {
          // 410 tells a removed camera to forget this main phone.
          if (registry.isRemovedToken(_token(req))) return await _json(req.response, 410, {'detail': 'removed'});
          return await _json(req.response, 401, {'detail': 'Invalid or revoked token'});
        }
        return await _json(req.response, 200, {'camera_id': device.cameraId, 'hub_name': displayName});
      }
      if (path == '/api/v1/events/motion' && req.method == 'POST') {
        return await _motionEvent(req);
      }
      if (path == '/api/v1/snapshots' && req.method == 'POST') {
        return await _snapshotUpload(req);
      }
      if (path == '/api/v1/control/ws') {
        return await _controlSocket(req);
      }
      const ingestPrefix = '/api/v1/streams/ingest/';
      if (path.startsWith(ingestPrefix)) {
        return await _ingestSocket(req, path.substring(ingestPrefix.length));
      }
      return await _json(req.response, 404, {'detail': 'Not found'});
    } catch (_) {
      try {
        return await _json(req.response, 500, {'detail': 'Internal error'});
      } catch (_) {}
    }
  }

  Future<void> _controlSocket(HttpRequest req) async {
    final device = registry.authenticate(_token(req));
    if (device == null) return _json(req.response, 401, {'detail': 'Invalid or revoked token'});
    if (!WebSocketTransformer.isUpgradeRequest(req)) {
      return _json(req.response, 400, {'detail': 'WebSocket upgrade required'});
    }
    final ws = await WebSocketTransformer.upgrade(req);
    await _controlSockets[device.deviceId]?.close(WebSocketStatus.normalClosure, 'replaced');
    _controlSockets[device.deviceId] = ws;
    final link = _linkFor(device)
      ..controlConnected = true
      ..lastSeenAt = DateTime.now()
      ..disconnectedAt = null
      ..droppedWhileStreaming = false;
    _notify();
    // The camera applies the settings chosen on this phone.
    _pushMotionSettings(device.deviceId, device.cameraId);
    _pushAiWatch(device.deviceId, device.cameraId);

    ws.listen(
      (msg) {
        if (msg is! String) return;
        Map<String, dynamic> data;
        try {
          data = Map<String, dynamic>.from(jsonDecode(msg) as Map);
        } catch (_) {
          return;
        }
        switch (data['type']) {
          case 'telemetry_report':
            final m = data['metrics'];
            if (m is Map) {
              link.lastSeenAt = DateTime.now();
              link.batteryLevel = (m['battery_level_percent'] as num?)?.toDouble() ?? link.batteryLevel;
              link.isCharging = m['is_charging'] as bool?;
              link.cameraFps = (m['encoder_fps'] as num?)?.toDouble();
              final rotation = (m['sensor_orientation'] as num?)?.toInt();
              if (rotation != null && rotation % 90 == 0) link.rotationDegrees = rotation % 360;
              _notify();
            }
          case 'ping':
            ws.add(jsonEncode({'type': 'pong', 'timestamp': data['timestamp']}));
        }
      },
      onDone: () {
        if (identical(_controlSockets[device.deviceId], ws)) {
          _controlSockets.remove(device.deviceId);
          final now = DateTime.now();
          final lastVideo = link.lastPacketAt;
          link
            ..controlConnected = false
            ..disconnectedAt = now
            ..droppedWhileStreaming = link.streaming || (lastVideo != null && now.difference(lastVideo).inSeconds < 10);
          _endMotion(link);
          _notify();
        }
      },
      cancelOnError: true,
    );
  }

  Future<void> _ingestSocket(HttpRequest req, String cameraId) async {
    final device = registry.authenticate(_token(req));
    if (device == null) return _json(req.response, 401, {'detail': 'Invalid or revoked token'});
    // A device may only stream as the camera it was paired as.
    if (device.cameraId != cameraId) {
      return _json(req.response, 403, {'detail': 'Token does not own this camera'});
    }
    if (!WebSocketTransformer.isUpgradeRequest(req)) {
      return _json(req.response, 400, {'detail': 'WebSocket upgrade required'});
    }
    final ws = await WebSocketTransformer.upgrade(req);
    await _ingestSockets[cameraId]?.close(WebSocketStatus.normalClosure, 'replaced');
    _ingestSockets[cameraId] = ws;
    final link = _linkFor(device)
      .._resetStream()
      ..streaming = true;
    _notify();

    var lastNotify = DateTime.now();
    ws.listen(
      (msg) {
        if (msg is! List<int>) return;
        final bytes = msg is Uint8List ? msg : Uint8List.fromList(msg);
        try {
          final packet = PacketDecoder.decode(bytes);
          link._recordPacket(packet.header, bytes.length);
          _packets.add(CameraPacket(cameraId, packet));
        } on PacketProtocolException {
          link.protocolErrors++;
        }
        final now = DateTime.now();
        if (now.difference(lastNotify).inMilliseconds >= 500) {
          lastNotify = now;
          _notify();
        }
      },
      onDone: () {
        if (identical(_ingestSockets[cameraId], ws)) {
          _ingestSockets.remove(cameraId);
          link._resetStream();
          _notify();
        }
      },
      cancelOnError: true,
    );
  }

  // ---------------------------------------------------------------- helpers

  CameraLink _linkFor(PairedDevice d) =>
      _links.putIfAbsent(d.cameraId, () => CameraLink(cameraId: d.cameraId, deviceId: d.deviceId, deviceName: d.deviceName))
        ..deviceName = d.deviceName;

  String? _token(HttpRequest req) {
    final auth = req.headers.value(HttpHeaders.authorizationHeader);
    if (auth != null && auth.toLowerCase().startsWith('bearer ')) return auth.substring(7).trim();
    return req.uri.queryParameters['token'];
  }

  /// Saves new per-camera settings and sends them to the camera if online.
  Future<void> updateCameraSettings(String cameraId, CameraSettings settings) async {
    await events?.updateSettings(cameraId, settings);
    final link = _links[cameraId];
    if (link != null) _pushMotionSettings(link.deviceId, cameraId);
    _notify();
  }

  /// Asks a camera for a JPEG of its current picture ("Ask AI now").
  /// Returns null if the camera is offline or does not answer in [timeout].
  Future<Uint8List?> requestSnapshot(String cameraId, {Duration timeout = const Duration(seconds: 6)}) async =>
      (await requestFrame(cameraId, timeout: timeout))?.jpeg;

  /// Like [requestSnapshot], also returning the camera's scene fingerprint.
  Future<CameraSnapshot?> requestFrame(String cameraId, {Duration timeout = const Duration(seconds: 6)}) async {
    final link = _links[cameraId];
    if (link == null) return null;
    final requestId = 'snap_${++_snapshotSeq}_${DateTime.now().millisecondsSinceEpoch}';
    final completer = Completer<CameraSnapshot?>();
    _snapshotRequests[requestId] = (cameraId, completer);
    final sent = sendCommand(link.deviceId, {
      'protocol': 'ss_control_v1',
      'type': 'device_control_command',
      'target_camera_id': cameraId,
      'action': 'capture_snapshot',
      'request_id': requestId,
    });
    if (!sent) {
      _snapshotRequests.remove(requestId);
      return null;
    }
    try {
      final snap = await completer.future.timeout(timeout, onTimeout: () => null);
      if (snap != null) {
        link
          ..lastPicture = snap.jpeg
          ..lastPictureAt = DateTime.now()
          ..lastPictureRotation = link.rotationDegrees;
      }
      return snap;
    } finally {
      _snapshotRequests.remove(requestId);
    }
  }

  /// Keeps each streaming camera's [CameraLink.lastPicture] at most [maxAge]
  /// old, so cards and the dashboard can show it once the camera stops.
  Future<void> refreshPictures({Duration maxAge = const Duration(seconds: 20)}) async {
    final now = DateTime.now();
    await Future.wait([
      for (final c in cameras)
        if (c.health(now) == CameraHealth.live && (c.lastPictureAt == null || now.difference(c.lastPictureAt!) >= maxAge))
          requestFrame(c.cameraId, timeout: const Duration(seconds: 4)),
    ]);
  }

  /// Renames a camera on this main phone (the camera keeps its own name).
  Future<bool> renameCamera(String cameraId, String name) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty || trimmed.length > 40) return false;
    final link = _links[cameraId];
    final device = registry.devices.where((d) => d.cameraId == cameraId).firstOrNull;
    if (device == null) return false;
    await registry.rename(device.deviceId, trimmed);
    link?.deviceName = trimmed;
    _notify();
    return true;
  }

  Future<void> _snapshotUpload(HttpRequest req) async {
    final device = registry.authenticate(_token(req));
    if (device == null) return _json(req.response, 401, {'detail': 'Invalid or revoked token'});
    final body = await _readJson(req, maxBytes: maxEventBodyBytes);
    if (body == null) return _json(req.response, 400, {'detail': 'Invalid JSON body'});
    final pending = _snapshotRequests[body['request_id']];
    // Only the camera that was asked may answer.
    if (pending == null || pending.$1 != device.cameraId) {
      return _json(req.response, 404, {'detail': 'Unknown or expired snapshot request'});
    }
    final completer = pending.$2;
    Uint8List jpeg;
    try {
      jpeg = base64Decode(body['snapshot_jpeg'] as String);
    } catch (_) {
      return _json(req.response, 400, {'detail': 'snapshot_jpeg is not valid base64'});
    }
    if (jpeg.length < 2 || jpeg[0] != 0xFF || jpeg[1] != 0xD8) {
      return _json(req.response, 400, {'detail': 'snapshot_jpeg is not a JPEG'});
    }
    Uint8List? grid;
    final rawGrid = body['grid'];
    if (rawGrid is String) {
      try {
        final g = base64Decode(rawGrid);
        if (g.length == 32 * 18) grid = g;
      } catch (_) {}
    }
    if (!completer.isCompleted) completer.complete(CameraSnapshot(jpeg, grid));
    return _json(req.response, 200, {'status': 'received'});
  }

  /// Tells a camera which AI watch tasks are active on it (privacy badge).
  void setAiWatch(String cameraId, List<String> taskLabels) {
    if (taskLabels.isEmpty) {
      _aiWatch.remove(cameraId);
    } else {
      _aiWatch[cameraId] = taskLabels;
    }
    final link = _links[cameraId];
    if (link != null) _pushAiWatch(link.deviceId, cameraId);
  }

  void _pushAiWatch(String deviceId, String cameraId) {
    sendCommand(deviceId, {
      'protocol': 'ss_control_v1',
      'type': 'device_control_command',
      'target_camera_id': cameraId,
      'action': 'set_ai_watch',
      'tasks': _aiWatch[cameraId] ?? const <String>[],
    });
  }

  void _pushMotionSettings(String deviceId, String cameraId) {
    final s = events?.settingsFor(cameraId) ?? const CameraSettings();
    sendCommand(deviceId, {
      'protocol': 'ss_control_v1',
      'type': 'device_control_command',
      'target_camera_id': cameraId,
      'action': 'set_motion',
      'enabled': s.motionEnabled,
      'sensitivity': s.sensitivity,
    });
  }

  void _endMotion(CameraLink link) {
    if (!link.motionActive) return;
    link.motionActive = false;
    link.activeEventId = null;
    events?.closeOngoing(link.cameraId);
  }

  /// Camera reports motion start (with snapshot) or end.
  ///   `{"phase":"started","score":0.12,"snapshot_jpeg":"BASE64"}` → `{"event_id":...}`
  ///   `{"phase":"ended","event_id":"...","peak_score":0.3}`
  Future<void> _motionEvent(HttpRequest req) async {
    final device = registry.authenticate(_token(req));
    if (device == null) return _json(req.response, 401, {'detail': 'Invalid or revoked token'});
    final body = await _readJson(req, maxBytes: maxEventBodyBytes);
    if (body == null) return _json(req.response, 400, {'detail': 'Invalid JSON body'});
    final link = _linkFor(device);

    switch (body['phase']) {
      case 'started':
        final score = (body['score'] as num?)?.toDouble() ?? 0;
        Uint8List? jpeg;
        final b64 = body['snapshot_jpeg'];
        if (b64 is String && b64.isNotEmpty) {
          try {
            jpeg = base64Decode(b64);
          } on FormatException {
            return _json(req.response, 400, {'detail': 'snapshot_jpeg is not valid base64'});
          }
          // JPEG files start with FF D8.
          if (jpeg.length < 2 || jpeg[0] != 0xFF || jpeg[1] != 0xD8) {
            return _json(req.response, 400, {'detail': 'snapshot_jpeg is not a JPEG'});
          }
        }
        if (events != null && !events!.settingsFor(link.cameraId).motionEnabled) {
          return _json(req.response, 202, {'ignored': true, 'reason': 'motion detection is off for this camera'});
        }
        final event = await events?.startMotion(
          cameraId: link.cameraId,
          cameraName: link.deviceName,
          score: score,
          rotationDegrees: link.rotationDegrees,
          snapshotJpeg: jpeg,
        );
        link
          ..motionActive = true
          ..activeEventId = event?.id;
        _notify();
        if (event != null) onMotionStarted?.call(event, link);
        return _json(req.response, 201, {'event_id': event?.id});
      case 'ended':
        final eventId = body['event_id'];
        if (eventId is String && events != null) {
          final ended = await events!.endMotion(
            eventId: eventId,
            cameraId: link.cameraId,
            peakScore: (body['peak_score'] as num?)?.toDouble(),
          );
          if (ended == null) return _json(req.response, 404, {'detail': 'No such event for this camera'});
        }
        link
          ..motionActive = false
          ..activeEventId = null;
        _notify();
        return _json(req.response, 200, {'status': 'ended'});
      default:
        return _json(req.response, 422, {'detail': 'phase must be "started" or "ended"'});
    }
  }

  Future<Map<String, dynamic>?> _readJson(HttpRequest req, {int maxBytes = maxJsonBodyBytes}) async {
    final builder = BytesBuilder(copy: false);
    await for (final chunk in req) {
      builder.add(chunk);
      if (builder.length > maxBytes) return null;
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

  void _notify() {
    if (!_changes.isClosed) _changes.add(null);
  }

  /// Best-effort LAN IPv4 address to show the user for manual pairing.
  static Future<String?> localIpAddress() async {
    final interfaces = await NetworkInterface.list(type: InternetAddressType.IPv4);
    String? fallback;
    for (final iface in interfaces) {
      for (final addr in iface.addresses) {
        if (addr.isLoopback) continue;
        final name = iface.name.toLowerCase();
        if (name.startsWith('wlan') || name.startsWith('en')) return addr.address;
        fallback ??= addr.address;
      }
    }
    return fallback;
  }
}
