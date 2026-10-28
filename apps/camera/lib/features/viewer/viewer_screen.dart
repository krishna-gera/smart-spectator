import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

import '../../core/ai/ai_client.dart';
import '../../core/platform/system_bridge.dart';
import '../../core/video/live_video_controller.dart';
import '../../hub/alert_service.dart';
import '../../hub/device_registry.dart';
import '../../hub/event_store.dart';
import '../../hub/hub_server.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import 'add_camera_screen.dart';
import 'events_view.dart';

/// Main phone: runs the local hub, shows live cameras, events and AI insights.
class ViewerScreen extends StatefulWidget {
  final VoidCallback onChangeRole;

  const ViewerScreen({super.key, required this.onChangeRole});

  @override
  State<ViewerScreen> createState() => _ViewerScreenState();
}

class _ViewerScreenState extends State<ViewerScreen> {
  late final DeviceRegistry _registry = DeviceRegistry(store: SharedPrefsDeviceStore());
  late final HubServer _server = HubServer(registry: _registry);
  final AiClient _ai = AiClient(AiConfig.fromEnvironment());
  final Map<String, LiveVideoController> _live = {};
  EventStore? _events;
  AlertService? _alerts;
  StreamSubscription<void>? _changesSub;
  Timer? _ticker;
  String? _localIp;
  String? _error;
  bool _ready = false;
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    try {
      await _registry.load();
      final support = await getApplicationSupportDirectory();
      final events = EventStore(dir: Directory('${support.path}/events'));
      await events.load();
      final alerts = AlertService(store: events, ai: _ai, notify: SystemBridge.notify);
      _events = events;
      _alerts = alerts;
      _server
        ..events = events
        ..onMotionStarted = (event, _) async {
          await alerts.onMotion(event);
          if (mounted) setState(() {});
        };
      await SystemBridge.requestNotificationPermission();
      await _server.start();
      _localIp = await HubServer.localIpAddress();
      _server.displayName = 'Main phone${_localIp != null ? ' ($_localIp)' : ''}';
      await SystemBridge.startHubService(text: 'Watching your cameras');
      await SystemBridge.advertiseHub(_server.boundPort!, _server.displayName);
      _changesSub = _server.changes.listen((_) {
        _syncLiveVideo();
        if (mounted) setState(() {});
      });
      _syncLiveVideo();
      _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) setState(() {});
      });
    } catch (e) {
      _error = 'The camera hub could not start: $e';
    }
    if (mounted) setState(() => _ready = true);
  }

  /// One decoder per streaming camera; released when the camera stops.
  void _syncLiveVideo() {
    final streaming = {for (final c in _server.cameras.where((c) => c.streaming)) c.cameraId};
    for (final id in _live.keys.where((id) => !streaming.contains(id)).toList()) {
      _live.remove(id)!.dispose();
    }
    for (final id in streaming.where((id) => !_live.containsKey(id))) {
      final controller = LiveVideoController(cameraId: id, packets: _server.packets, requestKeyframe: _server.requestKeyframe);
      _live[id] = controller;
      controller.start();
    }
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _changesSub?.cancel();
    for (final c in _live.values) {
      c.dispose();
    }
    _live.clear();
    _server.dispose();
    SystemBridge.stopAdvertisingHub();
    SystemBridge.stopHubService();
    super.dispose();
  }

  // ---------------------------------------------------------------- actions

  Future<void> _addCamera() async {
    final port = _server.boundPort;
    if (port == null) return;
    await Navigator.of(context).push(MaterialPageRoute<bool>(
      builder: (_) => AddCameraScreen(
        registry: _registry,
        hubPort: port,
        hubName: _server.displayName,
        hubCode: _registry.hubCode,
      ),
    ));
    if (mounted) setState(() {});
  }

  Future<void> _changeCode() async {
    if (await confirm(context,
        title: 'Change pairing code?',
        message: 'Cameras already connected stay connected. New cameras will need the new code.',
        action: 'Change')) {
      await _registry.changeHubCode();
      if (mounted) setState(() {});
    }
  }

  Future<void> _removeCamera(CameraLink cam) async {
    if (await confirm(context,
        title: 'Remove ${cam.deviceName}?',
        message: 'It will disconnect and must be added again with a code.',
        action: 'Remove',
        destructive: true)) {
      await _server.revokeDevice(cam.deviceId);
    }
  }

  void _openSettings(CameraLink cam) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => CameraSettingsSheet(
        cameraName: cam.deviceName,
        initial: _events?.settingsFor(cam.cameraId) ?? const CameraSettings(),
        aiConfigured: _ai.config.isConfigured,
        onChanged: (s) async {
          await _server.updateCameraSettings(cam.cameraId, s);
          if (mounted) setState(() {});
        },
      ),
    );
  }

  void _openLive(CameraLink cam) {
    final controller = _live[cam.cameraId];
    if (controller == null) return;
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => LiveCameraPage(
        camera: cam,
        controller: controller,
        aiConfigured: _ai.config.isConfigured,
        onAskAi: () => _askAi(cam),
      ),
    ));
  }

  /// "Ask AI now": take a fresh snapshot from the camera and describe it.
  Future<AiResult> _askAi(CameraLink cam) async {
    final alerts = _alerts;
    if (alerts == null) return const AiResult.failed('Not ready yet.');
    final jpeg = await _server.requestSnapshot(cam.cameraId);
    if (jpeg == null) return const AiResult.failed('The camera did not send a snapshot. Is it streaming?');
    final (_, result) = await alerts.analyzeSnapshot(
      cameraId: cam.cameraId,
      cameraName: cam.deviceName,
      jpeg: jpeg,
      rotationDegrees: cam.rotationDegrees,
    );
    if (mounted) setState(() {});
    return result;
  }

  // ---------------------------------------------------------------- UI

  @override
  Widget build(BuildContext context) {
    final unseen = _events?.unseenCount ?? 0;
    return Scaffold(
      appBar: AppBar(
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(_tab == 0 ? 'Cameras' : 'Events'),
          const SizedBox(height: 2),
          Text(
            _server.isRunning ? 'Main phone · ${_server.cameras.where((c) => c.streaming).length} live' : 'Starting…',
            style: const TextStyle(fontSize: 12, color: AppColors.textMuted, fontWeight: FontWeight.w500),
          ),
        ]),
        actions: [
          if (_tab == 0 && _server.isRunning)
            IconButton(icon: const Icon(Icons.add_circle_outline), tooltip: 'Add camera', onPressed: _addCamera),
          PopupMenuButton<String>(
            onSelected: (v) {
              if (v == 'role') widget.onChangeRole();
              if (v == 'code') _changeCode();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'code', child: Text('Change pairing code')),
              PopupMenuItem(value: 'role', child: Text('Use this phone as a camera')),
            ],
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: [
          const NavigationDestination(icon: Icon(Icons.videocam_outlined), selectedIcon: Icon(Icons.videocam), label: 'Cameras'),
          NavigationDestination(
            icon: Badge(isLabelVisible: unseen > 0, label: Text('$unseen'), child: const Icon(Icons.notifications_none)),
            selectedIcon: const Icon(Icons.notifications),
            label: 'Events',
          ),
        ],
      ),
      body: !_ready
          ? const Center(child: CircularProgressIndicator())
          : _tab == 1
              ? EventsView(store: _events, aiConfigured: _ai.config.isConfigured, onChanged: () => setState(() {}))
              : _camerasTab(),
    );
  }

  Widget _camerasTab() {
    final cameras = _server.cameras;
    final live = cameras.where((c) => _live.containsKey(c.cameraId)).toList();
    final address = _localIp != null && _server.boundPort != null ? '$_localIp:${_server.boundPort}' : null;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
      children: [
        if (_error != null)
          Card(
            color: AppColors.danger.withValues(alpha: 0.12),
            child: Padding(padding: const EdgeInsets.all(16), child: Text(_error!, style: const TextStyle(color: AppColors.danger))),
          ),
        if (cameras.isEmpty && _server.isRunning) ...[
          const SizedBox(height: 12),
          const EmptyState(
            icon: Icons.videocam_outlined,
            title: 'Add your first camera',
            message: 'Open Smart Spectator on another phone, choose Camera, and enter this code. '
                'Phones on the same Wi-Fi find each other automatically.',
          ),
          CodeDisplay(code: _registry.hubCode, caption: 'Pairing code for this main phone', onChange: _changeCode),
          const SizedBox(height: 12),
          OutlinedButton.icon(onPressed: _addCamera, icon: const Icon(Icons.pin_outlined), label: const Text('Add a camera by its code')),
        ],
        if (live.isNotEmpty) ...[
          const SectionHeader('Live'),
          LayoutBuilder(builder: (context, c) {
            final columns = c.maxWidth > 700 ? 3 : (live.length == 1 ? 1 : 2);
            return GridView.count(
              crossAxisCount: columns,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 10,
              crossAxisSpacing: 10,
              childAspectRatio: columns == 1 ? 16 / 10 : 3 / 4,
              children: [
                for (final cam in live)
                  GestureDetector(onTap: () => _openLive(cam), child: _LiveTile(camera: cam, controller: _live[cam.cameraId]!)),
              ],
            );
          }),
        ],
        if (cameras.isNotEmpty) ...[
          SectionHeader('All cameras (${cameras.length})',
              trailing: TextButton.icon(onPressed: _addCamera, icon: const Icon(Icons.add, size: 18), label: const Text('Add'))),
          for (final cam in cameras)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _CameraCard(
                camera: cam,
                settings: _events?.settingsFor(cam.cameraId) ?? const CameraSettings(),
                aiConfigured: _ai.config.isConfigured,
                onOpen: _live.containsKey(cam.cameraId) ? () => _openLive(cam) : null,
                onSettings: () => _openSettings(cam),
                onRemove: () => _removeCamera(cam),
              ),
            ),
          const SectionHeader('Connect more cameras'),
          CodeDisplay(code: _registry.hubCode, caption: 'Pairing code for this main phone', compact: true, onChange: _changeCode),
        ],
        if (address != null)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Text(
              'Keep Smart Spectator open while cameras stream. Address for manual setup: $address',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textFaint, fontSize: 12),
            ),
          ),
      ],
    );
  }
}

// ---------------------------------------------------------------- live video

/// Decoded video for one camera, rotated upright and letterboxed.
class LiveVideo extends StatelessWidget {
  final CameraLink camera;
  final LiveVideoController controller;
  const LiveVideo({super.key, required this.camera, required this.controller});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final id = controller.textureId;
        if (controller.state == LiveVideoState.failed) {
          return _VideoMessage(controller.error ?? 'Video unavailable');
        }
        if (id == null || controller.state != LiveVideoState.playing) {
          return const _VideoMessage('Connecting video…', spinner: true);
        }
        final quarterTurns = camera.rotationDegrees ~/ 90;
        final aspect = quarterTurns.isOdd ? 1 / controller.aspectRatio : controller.aspectRatio;
        return Center(
          child: AspectRatio(
            aspectRatio: aspect,
            child: RotatedBox(quarterTurns: quarterTurns, child: Texture(textureId: id)),
          ),
        );
      },
    );
  }
}

class _VideoMessage extends StatelessWidget {
  final String text;
  final bool spinner;
  const _VideoMessage(this.text, {this.spinner = false});

  @override
  Widget build(BuildContext context) => Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (spinner) const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)),
          const SizedBox(height: 8),
          Text(text, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
        ]),
      );
}

class _LiveTile extends StatelessWidget {
  final CameraLink camera;
  final LiveVideoController controller;
  const _LiveTile({required this.camera, required this.controller});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: ColoredBox(
        color: Colors.black,
        child: Stack(fit: StackFit.expand, children: [
          LiveVideo(camera: camera, controller: controller),
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: Container(
              padding: const EdgeInsets.fromLTRB(10, 18, 10, 8),
              decoration: const BoxDecoration(
                gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Colors.transparent, Colors.black87]),
              ),
              child: Text(camera.deviceName,
                  overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
            ),
          ),
          Positioned(
            left: 8,
            top: 8,
            child: Row(children: [
              const StatusChip('LIVE', color: AppColors.danger, filled: true),
              if (camera.motionActive) ...[
                const SizedBox(width: 6),
                const StatusChip('Motion', color: AppColors.warning, filled: true, icon: Icons.directions_run),
              ],
            ]),
          ),
        ]),
      ),
    );
  }
}

/// Full-screen live view. Rotates with the phone; landscape fills the screen.
class LiveCameraPage extends StatefulWidget {
  final CameraLink camera;
  final LiveVideoController controller;
  final bool aiConfigured;
  final Future<AiResult> Function() onAskAi;

  const LiveCameraPage({
    super.key,
    required this.camera,
    required this.controller,
    required this.aiConfigured,
    required this.onAskAi,
  });

  @override
  State<LiveCameraPage> createState() => _LiveCameraPageState();
}

class _LiveCameraPageState extends State<LiveCameraPage> {
  bool _asking = false;

  @override
  void initState() {
    super.initState();
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
  }

  @override
  void dispose() {
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  Future<void> _ask() async {
    setState(() => _asking = true);
    final result = await widget.onAskAi();
    if (!mounted) return;
    setState(() => _asking = false);
    showModalBottomSheet<void>(context: context, builder: (_) => AiResultSheet(cameraName: widget.camera.deviceName, result: result));
  }

  @override
  Widget build(BuildContext context) {
    return OrientationBuilder(builder: (context, orientation) {
      final landscape = orientation == Orientation.landscape;
      SystemChrome.setEnabledSystemUIMode(landscape ? SystemUiMode.immersiveSticky : SystemUiMode.edgeToEdge);
      final askButton = widget.aiConfigured
          ? FloatingActionButton.extended(
              onPressed: _asking ? null : _ask,
              backgroundColor: AppColors.ai,
              foregroundColor: Colors.black,
              icon: _asking
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                  : const Icon(Icons.auto_awesome),
              label: Text(_asking ? 'Asking AI…' : 'Ask AI'),
            )
          : null;

      return Scaffold(
        backgroundColor: Colors.black,
        extendBodyBehindAppBar: true,
        appBar: landscape
            ? null
            : AppBar(
                backgroundColor: Colors.transparent,
                title: Text(widget.camera.deviceName),
                actions: [
                  if (widget.camera.motionActive)
                    const Padding(padding: EdgeInsets.only(right: 12), child: StatusChip('Motion', color: AppColors.warning, filled: true)),
                ],
              ),
        floatingActionButton: askButton,
        body: Stack(fit: StackFit.expand, children: [
          LiveVideo(camera: widget.camera, controller: widget.controller),
          if (landscape)
            SafeArea(
              child: Align(
                alignment: Alignment.topLeft,
                child: IconButton.filledTonal(
                  icon: const Icon(Icons.arrow_back),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ),
            ),
        ]),
      );
    });
  }
}

/// Shows what the AI said about a snapshot.
class AiResultSheet extends StatelessWidget {
  final String cameraName;
  final AiResult result;
  const AiResultSheet({super.key, required this.cameraName, required this.result});

  @override
  Widget build(BuildContext context) {
    final i = result.insight;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.auto_awesome, color: AppColors.ai),
            const SizedBox(width: 8),
            Text('AI · $cameraName', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: 14),
          if (i == null)
            Text(result.error ?? 'No answer.', style: const TextStyle(color: AppColors.danger))
          else ...[
            Text(i.summary, style: const TextStyle(fontSize: 17, height: 1.4)),
            const SizedBox(height: 14),
            Wrap(spacing: 8, runSpacing: 8, children: [
              StatusChip(AlertService.categoryLabels[i.category] ?? i.category, color: AppColors.ai),
              if (i.peopleCount > 0) StatusChip('${i.peopleCount} ${i.peopleCount == 1 ? 'person' : 'people'}', color: AppColors.primary),
              StatusChip('Threat: ${i.threatLevel}',
                  color: i.threatLevel == 'high' ? AppColors.danger : (i.threatLevel == 'medium' ? AppColors.warning : AppColors.success)),
            ]),
            const SizedBox(height: 12),
            const Text('Saved to Events. AI descriptions can be wrong; check the snapshot.',
                style: TextStyle(color: AppColors.textFaint, fontSize: 12)),
          ],
        ]),
      ),
    );
  }
}

class _CameraCard extends StatelessWidget {
  final CameraLink camera;
  final CameraSettings settings;
  final bool aiConfigured;
  final VoidCallback? onOpen;
  final VoidCallback onSettings;
  final VoidCallback onRemove;

  const _CameraCard({
    required this.camera,
    required this.settings,
    required this.aiConfigured,
    required this.onOpen,
    required this.onSettings,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final last = camera.lastPacketAt;
    final live = camera.streaming && last != null && DateTime.now().difference(last).inSeconds < 3;
    final (label, color) = live
        ? ('Live', AppColors.success)
        : camera.streaming
            ? ('Connecting', AppColors.warning)
            : camera.controlConnected
                ? ('Online', AppColors.primary)
                : ('Offline', AppColors.textFaint);
    final details = <String>[
      if (camera.batteryLevel != null) '${camera.batteryLevel!.round()}% battery${camera.isCharging == true ? ' ⚡' : ''}',
      if (live) '${camera.bitrateKbps.toStringAsFixed(0)} kbps',
      settings.motionEnabled ? (camera.motionActive ? 'motion now' : 'motion on') : 'motion off',
      if (aiConfigured && settings.aiEnabled) 'AI on',
    ];

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onOpen,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 4, 12),
          child: Row(children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(color: color.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(12)),
              child: Icon(Icons.videocam, color: color),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Flexible(
                    child: Text(camera.deviceName,
                        overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                  ),
                  const SizedBox(width: 8),
                  StatusChip(label, color: color),
                ]),
                const SizedBox(height: 4),
                Text(details.join(' · '), style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
              ]),
            ),
            IconButton(icon: const Icon(Icons.tune), tooltip: 'Camera settings', onPressed: onSettings),
            IconButton(icon: const Icon(Icons.delete_outline), tooltip: 'Remove camera', onPressed: onRemove),
          ]),
        ),
      ),
    );
  }
}
