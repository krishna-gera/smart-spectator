import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../camera/camcorder_service.dart';
import '../../camera/camera_link_server.dart';
import '../../core/codec/h264_encoder.dart';
import '../../core/control/control_client.dart';
import '../../core/motion/motion_detector.dart';
import '../../core/motion/motion_reporter.dart';
import '../../core/pairing/pairing_client.dart';
import '../../core/protocol/packet_encoder.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/storage/credential_store.dart';
import '../../core/streaming/media_transport.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import 'allow_main_phone.dart';

/// Longest side of pictures sent to the main phone (motion events, AI checks,
/// "last picture"). Enough detail for the AI, far fewer tokens than full size.
const aiPictureSize = 640;

/// Connection to one main phone: video, control channel, motion reports.
class _HubConnection {
  final HubLink link;
  final MediaTransport media;
  final ControlClient control;
  final MotionReporter reporter;
  TransportStatus status = TransportStatus.disconnected;

  /// Control channel (battery, settings, snapshots) is up. It stays open
  /// while not streaming so the main phone always knows this camera's state.
  bool controlUp = false;
  Future<String?>? motionEventId;
  StreamSubscription<TransportStatus>? statusSub;

  _HubConnection(this.link, this.media, this.control, this.reporter);

  Future<void> connect() async {
    await media.connect();
    await control.start();
  }

  /// Stops the video only; the control channel stays connected.
  void disconnect() => media.disconnect();

  void dispose() {
    statusSub?.cancel();
    media.dispose();
    control.stop();
  }
}

/// Camcorder Mode: full-screen camera that streams to every linked main phone.
class CameraScreen extends StatefulWidget {
  final CamcorderService service;
  final VoidCallback onAddMainPhone;
  final VoidCallback onChangeRole;

  const CameraScreen({super.key, required this.service, required this.onAddMainPhone, required this.onChangeRole});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> with WidgetsBindingObserver {
  CameraController? _camera;
  bool _cameraReady = false;
  String? _cameraError;

  final H264HardwareEncoder _encoder = H264HardwareEncoder();
  final Map<String, _HubConnection> _hubs = {};
  bool _streaming = false;
  bool _processingFrame = false;
  int _sequence = 0;
  int _bytesSent = 0;
  double _fps = 0;
  DateTime _fpsWindowStart = DateTime.now();
  int _fpsFrames = 0;

  // Motion detection (no AI) on this phone; reported to every main phone.
  final MotionDetector _motion = MotionDetector();
  bool _motionEnabled = true;
  bool _motionActive = false;

  // What the AI does with this camera, per main phone (shown as a badge for
  // privacy): watch tasks, AI descriptions of motion snapshots, and when a
  // picture was last sent for "Ask AI".
  final Map<String, List<String>> _aiWatch = {};
  final Set<String> _aiDescribing = {};
  DateTime? _aiPictureAt;
  Timer? _aiPictureTimer;
  static const _aiPictureShownFor = Duration(seconds: 15);

  // "Ask AI now" requests waiting for the next frame: (connection key, request id).
  final List<(String, String)> _snapshotRequests = [];

  // A one-off picture taken while not streaming (for AI tasks).
  Future<void>? _still;

  // Whoever asked the owner before this screen opened (restored on close).
  Future<bool> Function(LinkRequest)? _previousApprover;

  // Power saver: a black screen while streaming untouched (OLED pixels off).
  static const _dimAfter = Duration(seconds: 30);
  bool _powerSaver = true;
  bool _dimmed = false;
  Timer? _dimTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.service.addListener(_syncHubs);
    _previousApprover = widget.service.approver;
    widget.service.approver = _askToAllow;
    _syncHubs();
    _initCamera();
    AppPrefs.powerSaver().then((on) {
      _powerSaver = on;
      _wake();
    });
  }

  void _wake() {
    _dimTimer?.cancel();
    if (_dimmed && mounted) setState(() => _dimmed = false);
    if (_powerSaver) _dimTimer = Timer(_dimAfter, () => mounted ? setState(() => _dimmed = true) : null);
  }

  /// The AI badge's label and what it covers, or null when no AI is in use.
  (String, String)? _aiBadge() {
    final tasks = _aiWatch.values.expand((t) => t).toList();
    final recent = _aiPictureAt != null && DateTime.now().difference(_aiPictureAt!) < _aiPictureShownFor;
    final reasons = [
      for (final t in tasks) 'Watch task: $t',
      if (_aiDescribing.isNotEmpty) 'Motion snapshots are sent to AI for a description',
      if (recent) 'A picture was just sent to AI',
    ];
    if (reasons.isEmpty) return null;
    return (tasks.isNotEmpty ? 'AI watching' : (_aiDescribing.isNotEmpty ? 'AI on' : 'AI checked'), reasons.join('\n'));
  }

  /// A main phone typed this camera's code: wake the screen and ask.
  Future<bool> _askToAllow(LinkRequest request) async {
    if (!mounted) return false;
    _wake();
    return askToAllowMainPhone(context, request);
  }

  Future<void> _setPowerSaver(bool on) async {
    await AppPrefs.setPowerSaver(on);
    setState(() => _powerSaver = on);
    _wake();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    widget.service.removeListener(_syncHubs);
    if (widget.service.approver == _askToAllow) widget.service.approver = _previousApprover;
    _dimTimer?.cancel();
    _aiPictureTimer?.cancel();
    _stopStreaming();
    for (final h in _hubs.values) {
      h.dispose();
    }
    _camera?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive || state == AppLifecycleState.paused) {
      if (_streaming) _stopStreaming();
      final cam = _camera;
      if (cam != null && cam.value.isInitialized) {
        _camera = null;
        cam.dispose();
        if (mounted) setState(() => _cameraReady = false);
      }
    } else if (state == AppLifecycleState.resumed && !_cameraReady) {
      _initCamera();
    }
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        if (mounted) setState(() => _cameraError = 'This device has no camera.');
        return;
      }
      final back = cameras.firstWhere((c) => c.lensDirection == CameraLensDirection.back, orElse: () => cameras.first);
      final controller =
          CameraController(back, ResolutionPreset.high, enableAudio: false, imageFormatGroup: ImageFormatGroup.yuv420);
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _camera = controller;
        _cameraReady = true;
        _cameraError = null;
      });
    } on CameraException catch (e) {
      if (mounted) {
        setState(() => _cameraError = e.code == 'CameraAccessDenied'
            ? 'Camera access is off. Allow it in Settings to use Camcorder Mode.'
            : 'Camera unavailable (${e.code}).');
      }
    }
  }

  /// Clockwise rotation the viewer must apply so the picture is upright.
  /// iOS already delivers frames in the phone's orientation; Android delivers
  /// them in the sensor's orientation, so the phone's own rotation is removed.
  int _rotationForViewer() {
    final cam = _camera;
    if (cam == null || Platform.isIOS) return 0;
    const degrees = {
      DeviceOrientation.portraitUp: 0,
      DeviceOrientation.landscapeLeft: 90,
      DeviceOrientation.portraitDown: 180,
      DeviceOrientation.landscapeRight: 270,
    };
    final device = degrees[cam.value.deviceOrientation] ?? 0;
    return (cam.description.sensorOrientation - device + 360) % 360;
  }

  // ---------------------------------------------------------------- main phones

  void _syncHubs() {
    final links = {for (final l in widget.service.hubs) l.key: l};
    for (final key in _hubs.keys.where((k) => !links.containsKey(k)).toList()) {
      _hubs.remove(key)!.dispose();
    }
    final deviceId = widget.service.credentials?.deviceId ?? '';
    for (final link in links.values.where((l) => !_hubs.containsKey(l.key))) {
      late final _HubConnection conn;
      conn = _HubConnection(
        link,
        MediaTransport(hubIp: link.hubHost, hubPort: link.hubPort, cameraId: link.cameraId, deviceToken: link.deviceToken),
        ControlClient(
          hubIp: link.hubHost,
          hubPort: link.hubPort,
          deviceId: deviceId,
          cameraId: link.cameraId,
          deviceToken: link.deviceToken,
          rotationProvider: _rotationForViewer,
          fpsProvider: () => _streaming ? _fps : null,
          onCommand: (cmd) => _onCommand(link.key, cmd),
          onConnectionChanged: (up) {
            conn.controlUp = up;
            if (mounted) setState(() {});
          },
          // The main phone may have a new Wi-Fi address: find it again.
          onUnreachable: () => widget.service.relocate(link),
        ),
        MotionReporter(hub: HubAddress(link.hubHost, link.hubPort), deviceToken: link.deviceToken),
      );
      conn.statusSub = conn.media.statusStream.listen((s) {
        conn.status = s;
        // Video cannot reach the main phone: its address may have changed.
        if (s == TransportStatus.reconnecting || s == TransportStatus.failed) widget.service.relocate(link);
        if (mounted) setState(() {});
      });
      _hubs[link.key] = conn;
      if (_streaming) {
        conn.connect();
      } else {
        conn.control.start();
      }
    }
    if (mounted) setState(() {});
  }

  void _onCommand(String hubKey, Map<String, dynamic> cmd) {
    switch (cmd['action']) {
      case 'request_idr':
        _encoder.requestKeyframe();
      case 'set_motion':
        final enabled = cmd['enabled'] != false;
        final sensitivity = (cmd['sensitivity'] as num?)?.toDouble();
        if (sensitivity != null) _motion.sensitivity = sensitivity.clamp(0.0, 1.0);
        if (!enabled && _motionActive) _finishMotion(0);
        if (!enabled) _motion.reset();
        if (mounted) setState(() => _motionEnabled = enabled);
      case 'set_ai_watch':
        final tasks = (cmd['tasks'] as List?)?.whereType<String>().toList() ?? const <String>[];
        final describing = cmd['descriptions'] == true;
        if (mounted) {
          setState(() {
            tasks.isEmpty ? _aiWatch.remove(hubKey) : _aiWatch[hubKey] = tasks;
            describing ? _aiDescribing.add(hubKey) : _aiDescribing.remove(hubKey);
          });
        }
      case 'capture_snapshot':
        final id = cmd['request_id'];
        if (cmd['for_ai'] == true && mounted) {
          setState(() => _aiPictureAt = DateTime.now());
          _aiPictureTimer?.cancel();
          _aiPictureTimer = Timer(_aiPictureShownFor, () => mounted ? setState(() {}) : null);
        }
        if (id is String) {
          _snapshotRequests.add((hubKey, id));
          // AI tasks and "Ask AI" also work while not streaming.
          if (!_streaming) _still ??= _captureStill().whenComplete(() => _still = null);
        }
    }
  }

  // ---------------------------------------------------------------- streaming

  /// Grabs one frame for pending snapshot requests without streaming video.
  Future<void> _captureStill() async {
    final cam = _camera;
    if (cam == null || !cam.value.isInitialized || cam.value.isStreamingImages) return;
    final done = Completer<void>();
    var frames = 0;
    try {
      await cam.startImageStream((image) {
        // Skip the first few frames so exposure settles.
        if (done.isCompleted || ++frames < 4) return;
        if (_snapshotRequests.isNotEmpty) _answerSnapshots(image);
        done.complete();
      });
      await done.future.timeout(const Duration(seconds: 4), onTimeout: () {});
    } catch (_) {
      // Camera busy; the main phone retries.
    } finally {
      try {
        if (!_streaming && cam.value.isStreamingImages) await cam.stopImageStream();
      } catch (_) {}
    }
  }

  Future<void> _startStreaming() async {
    await _still;
    final cam = _camera;
    if (cam == null || !cam.value.isInitialized || _hubs.isEmpty) return;
    for (final h in _hubs.values) {
      await h.connect();
    }
    _motion.reset();
    _sequence = 0;
    _bytesSent = 0;
    _fpsFrames = 0;
    _fpsWindowStart = DateTime.now();

    try {
      await cam.startImageStream(_onFrame);
      HapticFeedback.mediumImpact();
      if (mounted) setState(() => _streaming = true);
      _wake();
    } catch (_) {
      await _encoder.stop();
      if (mounted) _showMessage('Could not start the camera stream.');
    }
  }

  Future<void> _onFrame(CameraImage image) async {
    if (!_streaming || _processingFrame) return;
    _processingFrame = true;
    try {
      final now = DateTime.now();
      _fpsFrames++;
      final elapsed = now.difference(_fpsWindowStart).inMilliseconds;
      if (elapsed >= 1000) {
        _fps = _fpsFrames * 1000 / elapsed;
        _fpsFrames = 0;
        _fpsWindowStart = now;
        if (mounted) setState(() {});
      }

      if (_motionEnabled) _checkMotion(image, now);
      if (_snapshotRequests.isNotEmpty) _answerSnapshots(image);

      final packets = await _encoder.encodeImage(image, now.microsecondsSinceEpoch);
      for (final pkt in packets) {
        final wire = PacketEncoder.encodePacket(
          frameType: pkt.isKeyframe ? PacketEncoder.frameTypeIdr : PacketEncoder.frameTypeP,
          sequenceNumber: _sequence++,
          ptsUs: pkt.ptsUs,
          payload: pkt.data,
        );
        for (final h in _hubs.values) {
          h.media.sendPacket(wire);
        }
        _bytesSent += wire.length;
      }
    } on PlatformException {
      if (mounted) _showMessage('This phone could not start its video encoder (${image.width}×${image.height}).');
      unawaited(_stopStreaming());
    } catch (_) {
      // One bad frame must not stop the stream.
    } finally {
      _processingFrame = false;
    }
  }

  void _checkMotion(CameraImage image, DateTime now) {
    final luma = image.planes.first;
    final update = _motion.process(luma.bytes, image.width, image.height, luma.bytesPerRow, now);
    if (update == null) return;
    if (update.phase == MotionPhase.started) {
      if (mounted) setState(() => _motionActive = true);
      final jpeg = H264HardwareEncoder.snapshotJpeg(image, maxSize: aiPictureSize);
      for (final h in _hubs.values) {
        h.motionEventId = jpeg.then((j) => h.reporter.started(score: update.score, snapshotJpeg: j));
      }
    } else {
      _finishMotion(update.score);
    }
  }

  void _finishMotion(double peakScore) {
    if (mounted) setState(() => _motionActive = false);
    for (final h in _hubs.values) {
      final pending = h.motionEventId;
      h.motionEventId = null;
      pending?.then((id) {
        if (id != null) h.reporter.ended(eventId: id, peakScore: peakScore);
      });
    }
  }

  void _answerSnapshots(CameraImage image) {
    final requests = List.of(_snapshotRequests);
    _snapshotRequests.clear();
    // Brightness fingerprint lets the main phone skip AI checks of an unchanged scene.
    final luma = image.planes.first;
    final grid = MotionDetector.sceneGrid(luma.bytes, image.width, image.height, luma.bytesPerRow);
    H264HardwareEncoder.snapshotJpeg(image, quality: 75, maxSize: aiPictureSize).then((jpeg) {
      if (jpeg == null) return;
      for (final (hubKey, requestId) in requests) {
        _hubs[hubKey]?.reporter.uploadSnapshot(requestId: requestId, jpeg: jpeg, grid: grid);
      }
    });
  }


  Future<void> _stopStreaming() async {
    if (_motionActive) _finishMotion(0);
    _motion.reset();
    _snapshotRequests.clear();
    try {
      final cam = _camera;
      if (cam != null && cam.value.isStreamingImages) await cam.stopImageStream();
    } catch (_) {}
    await _encoder.stop();
    for (final h in _hubs.values) {
      h.disconnect();
    }
    if (mounted) {
      setState(() {
        _streaming = false;
        _fps = 0;
      });
    }
  }

  void _showMessage(String text) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  // ---------------------------------------------------------------- sheets

  void _openMainPhones() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => StatefulBuilder(builder: (ctx, setSheet) {
        final hubs = widget.service.hubs;
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Main phones', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              const Text('This camera streams to every main phone listed here.', style: TextStyle(color: AppColors.textMuted)),
              const SizedBox(height: 16),
              for (final link in hubs)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Card(
                    child: ListTile(
                      leading: Icon(Icons.phone_iphone, color: _statusColor(_hubs[link.key]?.status)),
                      title: Text(link.hubName),
                      subtitle: Text('${link.hubHost}:${link.hubPort} · ${_statusLabel(_hubs[link.key]?.status)}',
                          style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
                      trailing: IconButton(
                        tooltip: 'Disconnect this main phone',
                        icon: const Icon(Icons.close, color: AppColors.danger),
                        onPressed: () async {
                          if (await confirm(ctx,
                              title: 'Remove ${link.hubName}?',
                              message: 'This camera will stop streaming to it. You can add it again with a code.',
                              action: 'Remove',
                              destructive: true)) {
                            await widget.service.removeHub(link.key);
                            setSheet(() {});
                          }
                        },
                      ),
                    ),
                  ),
                ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: () {
                  Navigator.pop(ctx);
                  widget.onAddMainPhone();
                },
                icon: const Icon(Icons.add),
                label: const Text('Connect another main phone'),
              ),
            ]),
          ),
        );
      }),
    );
  }

  void _openCameraCode() {
    showModalBottomSheet<void>(
      context: context,
      builder: (ctx) => StatefulBuilder(builder: (ctx, setSheet) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Text('Add this camera to a main phone', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              const Text(
                'On the main phone open VYRO → Add camera and type this code, then tap Allow here. '
                'Several main phones can use the same code; you allow each one on this phone.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.textMuted, height: 1.4),
              ),
              const SizedBox(height: 16),
              CodeDisplay(
                code: widget.service.cameraCode,
                caption: '${widget.service.deviceName} · camera code',
                onChange: () async {
                  if (await confirm(ctx,
                      title: 'Change camera code?',
                      message: 'Main phones already connected stay connected. New ones need the new code.',
                      action: 'Change')) {
                    await widget.service.changeCameraCode();
                    setSheet(() {});
                  }
                },
              ),
            ]),
          ),
        );
      }),
    );
  }

  static Color _statusColor(TransportStatus? s) => switch (s) {
        TransportStatus.connected => AppColors.success,
        TransportStatus.connecting || TransportStatus.reconnecting => AppColors.warning,
        TransportStatus.failed => AppColors.danger,
        _ => AppColors.textFaint,
      };

  static String _statusLabel(TransportStatus? s) => switch (s) {
        TransportStatus.connected => 'receiving video',
        TransportStatus.connecting => 'connecting…',
        TransportStatus.reconnecting => 'reconnecting…',
        TransportStatus.failed => 'not reachable',
        _ => 'idle',
      };

  // ---------------------------------------------------------------- UI

  @override
  Widget build(BuildContext context) {
    final connected = _hubs.values.where((h) => h.status == TransportStatus.connected).length;
    final total = _hubs.length;

    return Scaffold(
      backgroundColor: Colors.black,
      body: Listener(
        behavior: HitTestBehavior.translucent,
        onPointerDown: (_) => _wake(),
        child: Stack(children: [
          Positioned.fill(child: _layout(connected, total)),
          Positioned.fill(
            child: IgnorePointer(
              ignoring: !_dimmed,
              child: AnimatedOpacity(
                opacity: _dimmed ? 1 : 0,
                duration: const Duration(milliseconds: 600),
                child: _PowerSaverView(streaming: _streaming, connected: connected, total: total, motionActive: _motionActive),
              ),
            ),
          ),
        ]),
      ),
    );
  }

  Widget _layout(int connected, int total) {
    return Builder(builder: (context) {
      return OrientationBuilder(builder: (context, orientation) {
        final landscape = orientation == Orientation.landscape;
        final preview = _CameraView(camera: _camera, ready: _cameraReady, error: _cameraError);
        final controls = _ControlsPanel(
          streaming: _streaming,
          canStream: _cameraReady && total > 0,
          fps: _fps,
          megabytes: _bytesSent / (1024 * 1024),
          connected: connected,
          total: total,
          onToggle: () {
            if (_streaming) HapticFeedback.lightImpact();
            _streaming ? _stopStreaming() : _startStreaming();
          },
          powerSaver: _powerSaver,
          onPowerSaver: _setPowerSaver,
          onMainPhones: _openMainPhones,
          onCameraCode: _openCameraCode,
          vertical: landscape,
        );
        final topBar = _TopBar(
          name: widget.service.deviceName,
          streaming: _streaming,
          motionEnabled: _motionEnabled,
          motionActive: _motionActive,
          ai: _aiBadge(),
          reconnecting: _streaming && _hubs.values.any((h) => h.status == TransportStatus.reconnecting || h.status == TransportStatus.failed),
          mainPhoneOffline: total > 0 && !_streaming && !_hubs.values.any((h) => h.controlUp),
          onChangeRole: widget.onChangeRole,
        );

        if (landscape) {
          return Row(children: [
            Expanded(child: Stack(fit: StackFit.expand, children: [preview, SafeArea(child: topBar)])),
            SizedBox(width: 300, child: SafeArea(left: false, child: controls)),
          ]);
        }
        return Column(children: [
          Expanded(child: Stack(fit: StackFit.expand, children: [preview, SafeArea(bottom: false, child: topBar)])),
          SafeArea(top: false, child: controls),
        ]);
      });
    });
  }
}

/// Black screen shown while streaming untouched; OLED screens use almost no
/// power for black. Any tap wakes the normal view.
class _PowerSaverView extends StatelessWidget {
  final bool streaming;
  final int connected;
  final int total;
  final bool motionActive;
  const _PowerSaverView({required this.streaming, required this.connected, required this.total, required this.motionActive});

  @override
  Widget build(BuildContext context) => ColoredBox(
        color: Colors.black,
        child: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Opacity(opacity: 0.55, child: VyroLogo(size: 54)),
            const SizedBox(height: 18),
            Row(mainAxisSize: MainAxisSize.min, children: [
              Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(color: streaming ? AppColors.danger : AppColors.success, shape: BoxShape.circle)),
              const SizedBox(width: 8),
              Text(streaming ? 'Streaming to $connected of $total main phone${total == 1 ? '' : 's'}' : 'Camera ready · VYRO stays on',
                  style: const TextStyle(color: AppColors.textFaint, fontSize: 14)),
            ]),
            if (motionActive) ...[
              const SizedBox(height: 8),
              const Text('Motion detected', style: TextStyle(color: AppColors.warning, fontSize: 13)),
            ],
            const SizedBox(height: 26),
            const Text('Power saver · tap to wake', style: TextStyle(color: Color(0xFF4A4E58), fontSize: 12.5)),
          ]),
        ),
      );
}

class _CameraView extends StatelessWidget {
  final CameraController? camera;
  final bool ready;
  final String? error;
  const _CameraView({required this.camera, required this.ready, required this.error});

  @override
  Widget build(BuildContext context) {
    if (error != null) {
      return EmptyState(icon: Icons.no_photography_outlined, title: 'Camera unavailable', message: error!);
    }
    final cam = camera;
    if (!ready || cam == null) return const Center(child: CircularProgressIndicator());
    // CameraPreview follows the phone's rotation; centre it without distortion.
    return Center(child: CameraPreview(cam));
  }
}

class _TopBar extends StatelessWidget {
  final String name;
  final bool streaming;
  final bool motionEnabled;
  final bool motionActive;
  /// AI badge label and details (null: no AI in use on this camera).
  final (String, String)? ai;
  final bool reconnecting;
  final bool mainPhoneOffline;
  final VoidCallback onChangeRole;
  const _TopBar({
    required this.name,
    required this.streaming,
    required this.motionEnabled,
    required this.motionActive,
    required this.ai,
    required this.reconnecting,
    required this.mainPhoneOffline,
    required this.onChangeRole,
  });

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 8, 0),
        child: Row(children: [
          const VyroLogo(size: 26),
          const SizedBox(width: 10),
          StatusChip(streaming ? 'LIVE' : 'READY', color: streaming ? AppColors.danger : AppColors.textMuted, filled: streaming),
          const SizedBox(width: 8),
          if (ai != null) ...[
            Tooltip(
              message: ai!.$2,
              child: StatusChip(ai!.$1, color: AppColors.ai, filled: true, icon: Icons.auto_awesome),
            ),
            const SizedBox(width: 8),
          ],
          if (reconnecting) ...[
            const StatusChip('Reconnecting…', color: AppColors.warning, icon: Icons.sync_rounded),
            const SizedBox(width: 8),
          ] else if (mainPhoneOffline) ...[
            const StatusChip('Main phone offline', color: AppColors.textMuted, icon: Icons.wifi_off_rounded),
            const SizedBox(width: 8),
          ],
          if (streaming && !reconnecting)
            StatusChip(
              !motionEnabled ? 'Motion off' : (motionActive ? 'Motion' : 'Watching'),
              color: motionActive ? AppColors.warning : AppColors.textMuted,
              icon: Icons.directions_run,
            ),
          const Spacer(),
          Container(
            decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.5), borderRadius: BorderRadius.circular(12)),
            child: Row(children: [
              Padding(
                padding: const EdgeInsets.only(left: 12),
                child: Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
              ),
              IconButton(icon: const Icon(Icons.swap_horiz), tooltip: 'Change phone mode', onPressed: onChangeRole),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _ControlsPanel extends StatelessWidget {
  final bool streaming;
  final bool canStream;
  final double fps;
  final double megabytes;
  final int connected;
  final int total;
  final VoidCallback onToggle;
  final VoidCallback onMainPhones;
  final VoidCallback onCameraCode;
  final bool vertical;
  final bool powerSaver;
  final ValueChanged<bool> onPowerSaver;

  const _ControlsPanel({
    required this.streaming,
    required this.canStream,
    required this.fps,
    required this.megabytes,
    required this.connected,
    required this.total,
    required this.onToggle,
    required this.onMainPhones,
    required this.onCameraCode,
    required this.vertical,
    required this.powerSaver,
    required this.onPowerSaver,
  });

  @override
  Widget build(BuildContext context) {
    final stats = streaming
        ? '${fps.toStringAsFixed(0)} fps · ${megabytes.toStringAsFixed(1)} MB sent'
        : (total == 0 ? 'Not connected to a main phone yet' : 'Ready to stream');
    final phones = total == 0
        ? 'No main phone'
        : (streaming ? '$connected of $total receiving' : '$total main phone${total == 1 ? '' : 's'}');

    final mainPhones = OutlinedButton.icon(
      onPressed: onMainPhones,
      icon: const Icon(Icons.devices, size: 18),
      label: Text(phones, overflow: TextOverflow.ellipsis),
    );
    final cameraCode = OutlinedButton.icon(
      onPressed: onCameraCode,
      icon: const Icon(Icons.pin_outlined, size: 18),
      label: const Text('Camera code'),
    );

    return Container(
      color: AppColors.background,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text(stats, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: canStream || streaming ? onToggle : null,
          style: FilledButton.styleFrom(backgroundColor: streaming ? AppColors.danger : AppColors.primary),
          icon: Icon(streaming ? Icons.stop_rounded : Icons.fiber_manual_record),
          label: Text(streaming ? 'Stop streaming' : 'Start streaming'),
        ),
        const SizedBox(height: 10),
        if (vertical) ...[
          mainPhones,
          const SizedBox(height: 10),
          cameraCode,
        ] else
          Row(children: [Expanded(child: mainPhones), const SizedBox(width: 10), Expanded(child: cameraCode)]),
        const SizedBox(height: 2),
        SwitchListTile(
          dense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 4),
          title: const Text('Power saver'),
          subtitle: const Text('Black screen after 30 s untouched (VYRO keeps running)', style: TextStyle(color: AppColors.textFaint, fontSize: 12)),
          value: powerSaver,
          onChanged: onPowerSaver,
        ),
      ]),
    );
  }
}
