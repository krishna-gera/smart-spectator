import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../camera/camcorder_service.dart';
import '../../core/codec/h264_encoder.dart';
import '../../core/control/control_client.dart';
import '../../core/motion/motion_detector.dart';
import '../../core/motion/motion_reporter.dart';
import '../../core/pairing/pairing_client.dart';
import '../../core/platform/system_bridge.dart';
import '../../core/protocol/packet_encoder.dart';
import '../../core/storage/credential_store.dart';
import '../../core/streaming/media_transport.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';

/// Connection to one main phone: video, control channel, motion reports.
class _HubConnection {
  final HubLink link;
  final MediaTransport media;
  final ControlClient control;
  final MotionReporter reporter;
  TransportStatus status = TransportStatus.disconnected;
  Future<String?>? motionEventId;
  StreamSubscription<TransportStatus>? statusSub;

  _HubConnection(this.link, this.media, this.control, this.reporter);

  Future<void> connect() async {
    await media.connect();
    await control.start();
  }

  void disconnect() {
    media.disconnect();
    control.stop();
  }

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

  // AI watch tasks per main phone (shown as a badge for privacy).
  final Map<String, List<String>> _aiWatch = {};

  // "Ask AI now" requests waiting for the next frame: (connection key, request id).
  final List<(String, String)> _snapshotRequests = [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.service.addListener(_syncHubs);
    _syncHubs();
    _initCamera();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    widget.service.removeListener(_syncHubs);
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
      _hubs.remove(key)!
        ..disconnect()
        ..dispose();
    }
    final deviceId = widget.service.credentials?.deviceId ?? '';
    for (final link in links.values.where((l) => !_hubs.containsKey(l.key))) {
      final conn = _HubConnection(
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
        ),
        MotionReporter(hub: HubAddress(link.hubHost, link.hubPort), deviceToken: link.deviceToken),
      );
      conn.statusSub = conn.media.statusStream.listen((s) {
        conn.status = s;
        if (mounted) setState(() {});
      });
      _hubs[link.key] = conn;
      if (_streaming) conn.connect();
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
        if (mounted) setState(() => tasks.isEmpty ? _aiWatch.remove(hubKey) : _aiWatch[hubKey] = tasks);
      case 'capture_snapshot':
        final id = cmd['request_id'];
        if (id is String) _snapshotRequests.add((hubKey, id));
    }
  }

  // ---------------------------------------------------------------- streaming

  Future<void> _startStreaming() async {
    final cam = _camera;
    if (cam == null || !cam.value.isInitialized || _hubs.isEmpty) return;
    for (final h in _hubs.values) {
      await h.connect();
    }
    await SystemBridge.keepScreenOn(true);
    _motion.reset();
    _sequence = 0;
    _bytesSent = 0;
    _fpsFrames = 0;
    _fpsWindowStart = DateTime.now();

    try {
      await cam.startImageStream(_onFrame);
      if (mounted) setState(() => _streaming = true);
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
      final jpeg = H264HardwareEncoder.snapshotJpeg(image);
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
    H264HardwareEncoder.snapshotJpeg(image, quality: 80).then((jpeg) {
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
    await SystemBridge.keepScreenOn(false);
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
                'On the main phone open Cameras → Add camera, pick this camera and enter its code. '
                'Several main phones can use the same code.',
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
      body: OrientationBuilder(builder: (context, orientation) {
        final landscape = orientation == Orientation.landscape;
        final preview = _CameraView(camera: _camera, ready: _cameraReady, error: _cameraError);
        final controls = _ControlsPanel(
          streaming: _streaming,
          canStream: _cameraReady && total > 0,
          fps: _fps,
          megabytes: _bytesSent / (1024 * 1024),
          connected: connected,
          total: total,
          onToggle: _streaming ? _stopStreaming : _startStreaming,
          onMainPhones: _openMainPhones,
          onCameraCode: _openCameraCode,
          vertical: landscape,
        );
        final topBar = _TopBar(
          name: widget.service.deviceName,
          streaming: _streaming,
          motionEnabled: _motionEnabled,
          motionActive: _motionActive,
          aiWatching: _aiWatch.values.expand((t) => t).toList(),
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
      }),
    );
  }
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
  final List<String> aiWatching;
  final VoidCallback onChangeRole;
  const _TopBar({
    required this.name,
    required this.streaming,
    required this.motionEnabled,
    required this.motionActive,
    required this.aiWatching,
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
          if (aiWatching.isNotEmpty) ...[
            Tooltip(
              message: 'AI is watching: ${aiWatching.join('; ')}',
              child: const StatusChip('AI watching', color: AppColors.ai, filled: true, icon: Icons.auto_awesome),
            ),
            const SizedBox(width: 8),
          ],
          if (streaming)
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
      ]),
    );
  }
}
