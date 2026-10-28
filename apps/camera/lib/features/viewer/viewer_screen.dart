import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

import '../../core/ai/ai_client.dart';
import '../../core/platform/system_bridge.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/video/live_video_controller.dart';
import '../../hub/alert_service.dart';
import '../../hub/camera_health.dart';
import '../../hub/device_registry.dart';
import '../../hub/event_store.dart';
import '../../hub/hub_server.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import '../../hub/watch_tasks.dart';
import '../onboarding/onboarding_screen.dart';
import 'add_camera_screen.dart';
import 'camera_card.dart';
import 'settings_screen.dart';
import 'task_editor_screen.dart';
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
  TaskWatcher? _tasks;
  StreamSubscription<void>? _tasksSub;
  StreamSubscription<void>? _changesSub;
  Timer? _ticker;
  int _ticks = 0;
  late final CameraHealthMonitor _health = CameraHealthMonitor(notify: SystemBridge.notify);
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
      final taskStore = TaskStore(Directory('${support.path}/events'));
      await taskStore.load();
      _tasks = TaskWatcher(
        store: taskStore,
        events: events,
        ai: _ai,
        snapshot: (id) => _server.requestFrame(id, timeout: const Duration(seconds: 5)),
        rotationOf: (id) => _server.cameras.where((c) => c.cameraId == id).firstOrNull?.rotationDegrees ?? 0,
        notify: SystemBridge.notify,
        onWatchChanged: _server.setAiWatch,
      );
      _server
        ..events = events
        ..onMotionStarted = (event, _) async {
          await alerts.onMotion(event);
          if (mounted) setState(() {});
        };
      await SystemBridge.requestNotificationPermission();
      // Browser dashboard at http://<this phone>:8000/ (sign in with the pairing code).
      _server.web
        ..aiAvailable = _ai.config.isConfigured
        ..tasks = _tasks
        ..onAskAi = (cameraId) async {
          final cam = _server.cameras.where((c) => c.cameraId == cameraId).firstOrNull;
          return cam == null ? const AiResult.failed('Unknown camera.') : _askAi(cam);
        };
      await _server.start();
      _tasks!.start();
      _tasksSub = _tasks!.changes.listen((_) {
        if (mounted) setState(() {});
      });
      _localIp = await HubServer.localIpAddress();
      _server.displayName = 'Main phone${_localIp != null ? ' ($_localIp)' : ''}';
      await SystemBridge.startHubService(text: 'Watching your cameras');
      await SystemBridge.advertiseHub(_server.boundPort!, _server.displayName);
      _changesSub = _server.changes.listen((_) {
        _syncLiveVideo();
        if (mounted) setState(() {});
      });
      _syncLiveVideo();
      _health.enabled = await AppPrefs.healthAlerts();
      _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
        _ticks++;
        // Keep a recent picture of each live camera for when it stops.
        if (_ticks % 10 == 0) _server.refreshPictures();
        if (_ticks % 5 == 0) _health.check(_server.cameras);
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
    _tasksSub?.cancel();
    _tasks?.dispose();
    _server.dispose();
    SystemBridge.stopAdvertisingHub();
    SystemBridge.stopHubService();
    super.dispose();
  }

  // ---------------------------------------------------------------- actions

  Future<void> _newTask({String? cameraId}) async {
    final tasks = _tasks;
    if (tasks == null) return;
    await Navigator.of(context).push(MaterialPageRoute<bool>(
      builder: (_) => TaskEditorScreen(watcher: tasks, cameras: _server.cameras, initialCameraId: cameraId),
    ));
    if (mounted) setState(() {});
  }

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

  Future<void> _renameCamera(CameraLink cam) async {
    final controller = TextEditingController(text: cam.deviceName);
    final name = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Rename camera', style: TextStyle(fontWeight: FontWeight.w800)),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 40,
          textCapitalization: TextCapitalization.words,
          decoration: const InputDecoration(hintText: 'e.g. Laundry room'),
          onSubmitted: (v) => Navigator.pop(ctx, v),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, controller.text), child: const Text('Save')),
        ],
      ),
    );
    controller.dispose();
    if (name == null || name.trim().isEmpty || name.trim() == cam.deviceName) return;
    if (await _server.renameCamera(cam.cameraId, name)) {
      HapticFeedback.lightImpact();
      if (mounted) setState(() {});
    }
  }

  void _showGuide() {
    Navigator.of(context).push(MaterialPageRoute<void>(
      fullscreenDialog: true,
      builder: (ctx) => OnboardingScreen(onDone: () => Navigator.of(ctx).pop()),
    ));
  }

  Future<void> _openSettingsScreen() async {
    final address = _localIp != null && _server.boundPort != null ? '$_localIp:${_server.boundPort}' : null;
    await Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => SettingsScreen(
        cameras: () => _server.cameras,
        pairingCode: () => _registry.hubCode,
        onChangeCode: _changeCode,
        onCameraSettings: _openSettings,
        onRename: _renameCamera,
        onRemove: _removeCamera,
        healthAlerts: _health.enabled,
        onHealthAlerts: (on) {
          _health.enabled = on;
          AppPrefs.setHealthAlerts(on);
        },
        dashboardAddress: address,
        aiConfigured: _ai.config.isConfigured,
        onShowGuide: _showGuide,
        onChangeRole: () {
          Navigator.of(context).pop();
          widget.onChangeRole();
        },
      ),
    ));
    if (mounted) setState(() {});
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
        leading: IconButton(
          icon: const Icon(Icons.swap_horiz_rounded),
          tooltip: 'Use this phone as a camera',
          onPressed: widget.onChangeRole,
        ),
        title: VyroTitle(subtitle: _tab == 0 ? 'Main phone' : 'Events'),
        actions: [
          IconButton(icon: const Icon(Icons.settings_outlined), tooltip: 'Settings', onPressed: _ready ? _openSettingsScreen : null),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) {
          if (i != _tab) HapticFeedback.selectionClick();
          setState(() => _tab = i);
        },
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

  List<Widget> _aiTasksSection() {
    final watcher = _tasks!;
    final tasks = watcher.store.tasks;
    return [
      const CenteredLabel('AI tasks', icon: Icons.auto_awesome, iconColor: AppColors.ai),
      if (tasks.isEmpty)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Text(
              _ai.config.isConfigured
                  ? 'Give a camera a job in plain words — "tell me when the washing machine is full" or '
                      '"notify me when the laptop download finishes" — and the AI watches for it.'
                  : 'AI tasks need the AI service, which is not set up in this build.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textMuted, height: 1.4),
            ),
          ),
        ),
      for (final t in tasks)
        Padding(padding: const EdgeInsets.only(bottom: 12), child: _TaskCard(task: t, watcher: watcher)),
      Padding(
        padding: const EdgeInsets.only(top: 4),
        child: OutlinedButton.icon(
          onPressed: _ai.config.isConfigured ? () => _newTask() : null,
          icon: const Icon(Icons.auto_awesome, color: AppColors.ai, size: 18),
          label: const Text('New AI task'),
        ),
      ),
    ];
  }

  Widget _camerasTab() {
    final cameras = _server.cameras;
    final live = cameras.where((c) => _live.containsKey(c.cameraId)).toList();
    final address = _localIp != null && _server.boundPort != null ? '$_localIp:${_server.boundPort}' : null;

    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 4, 18, 28),
      children: [
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Card(
              color: AppColors.danger.withValues(alpha: 0.14),
              child: Padding(padding: const EdgeInsets.all(16), child: Text(_error!, style: const TextStyle(color: AppColors.danger))),
            ),
          ),
        RingHeader(
          icon: Icons.videocam_rounded,
          color: AppColors.ringCameras,
          progress: cameras.isEmpty ? 0 : live.length / cameras.length,
          title: cameras.isEmpty ? 'No cameras yet' : 'Camera status',
          countStrong: cameras.isEmpty ? null : '${live.length}/${cameras.length}',
          countRest: cameras.isEmpty ? 'Turn a spare phone into a camera' : 'cameras live',
        ),
        if (_server.isRunning)
          ActionBanner(
            title: 'Add camera',
            subtitle: cameras.isEmpty ? 'Pair a phone with this code or by its camera code' : 'Pair another phone in seconds',
            icon: Icons.add_rounded,
            onTap: _addCamera,
          ),
        if (cameras.isEmpty && _server.isRunning) ...[
          const SizedBox(height: 16),
          CodeDisplay(
            code: _registry.hubCode,
            caption: 'On the camera phone choose Camera and enter this code',
            onChange: _changeCode,
          ),
        ],
        if (cameras.isNotEmpty) ...[
          const CenteredLabel('Cameras', icon: Icons.videocam_outlined),
          LayoutBuilder(builder: (context, c) {
            final columns = c.maxWidth > 760 ? 2 : 1;
            final cards = [
              for (final cam in cameras)
                CameraCard(
                  key: ValueKey(cam.cameraId),
                  camera: cam,
                  controller: _live[cam.cameraId],
                  settings: _events?.settingsFor(cam.cameraId) ?? const CameraSettings(),
                  aiConfigured: _ai.config.isConfigured,
                  onOpen: _live.containsKey(cam.cameraId) ? () => _openLive(cam) : null,
                  onSettings: () => _openSettings(cam),
                  onRename: () => _renameCamera(cam),
                  onRemove: () => _removeCamera(cam),
                  onWatch: _ai.config.isConfigured ? () => _newTask(cameraId: cam.cameraId) : null,
                ),
            ];
            if (columns == 1) {
              return Column(children: [for (final card in cards) Padding(padding: const EdgeInsets.only(bottom: 14), child: card)]);
            }
            return Wrap(spacing: 14, runSpacing: 14, children: [
              for (final card in cards) SizedBox(width: (c.maxWidth - 14) / 2, child: card),
            ]);
          }),
        ],
        if (cameras.isNotEmpty && _tasks != null) ..._aiTasksSection(),
        if (cameras.isNotEmpty) ...[
          const CenteredLabel('Pairing code', icon: Icons.key_rounded),
          CodeDisplay(code: _registry.hubCode, caption: 'Enter this on a camera phone to connect it', compact: true, onChange: _changeCode),
        ],
        if (address != null)
          Padding(
            padding: const EdgeInsets.only(top: 18),
            child: Text(
              'Keep VYRO open while cameras stream.\nWeb dashboard and manual setup: http://$address',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textFaint, fontSize: 12, height: 1.5),
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

/// One AI watch task: progress ring, status, the AI's latest observation, actions.
class _TaskCard extends StatelessWidget {
  final WatchTask task;
  final TaskWatcher watcher;
  const _TaskCard({required this.task, required this.watcher});

  @override
  Widget build(BuildContext context) {
    final t = task;
    final now = DateTime.now();
    final done = t.status == TaskStatus.done;
    final active = t.status == TaskStatus.watching;
    final progress = done ? 1.0 : ((t.lastProgress ?? (active ? 5 : 0)) / 100);
    final color = done ? AppColors.success : (active ? AppColors.ai : AppColors.textFaint);

    Widget action(String label, IconData icon, VoidCallback onTap, {bool primary = false}) => Expanded(
          child: primary
              ? FilledButton.icon(
                  onPressed: onTap,
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(44)),
                  icon: Icon(icon, size: 18),
                  label: Text(label),
                )
              : OutlinedButton.icon(
                  onPressed: onTap,
                  style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(44)),
                  icon: Icon(icon, size: 18),
                  label: Text(label),
                ),
        );

    final actions = <Widget>[
      if (t.needsAcknowledgement)
        action('Handled', Icons.check_rounded, () {
          HapticFeedback.mediumImpact();
          watcher.acknowledge(t);
        }, primary: true),
      if (active) action('Pause', Icons.pause_rounded, () => watcher.pause(t)),
      if (t.status == TaskStatus.paused) action('Resume', Icons.play_arrow_rounded, () => watcher.resume(t), primary: true),
      if (!active && t.status != TaskStatus.paused && !t.needsAcknowledgement)
        action('Watch again', Icons.replay_rounded, () => watcher.resume(t)),
      action(active ? 'Stop' : 'Delete', active ? Icons.stop_rounded : Icons.delete_outline_rounded, () async {
        if (active) {
          await watcher.stopTask(t);
        } else if (await confirm(context, title: 'Delete this task?', message: t.description, action: 'Delete', destructive: true)) {
          await watcher.delete(t);
        }
      }),
    ];

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            ProgressRing(icon: done ? Icons.check_rounded : Icons.auto_awesome, color: color, progress: progress),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(t.description, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, height: 1.3)),
                const SizedBox(height: 4),
                Text('${t.cameraName}${t.lastProgress != null && t.progressApplicable ? ' · ~${t.lastProgress}%' : ''}',
                    style: const TextStyle(color: AppColors.textMuted, fontSize: 13.5)),
              ]),
            ),
            CheckCircle(checked: done, size: 26),
          ]),
          if (t.lastObservation != null && t.lastObservation!.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text('“${t.lastObservation}”', style: const TextStyle(color: AppColors.text, fontSize: 14, height: 1.35)),
          ],
          const SizedBox(height: 10),
          const Divider(),
          const SizedBox(height: 10),
          Row(children: [
            Icon(t.lastError != null ? Icons.error_outline_rounded : Icons.schedule_rounded,
                size: 18, color: t.lastError != null || t.needsAcknowledgement ? AppColors.danger : AppColors.textMuted),
            const SizedBox(width: 8),
            Expanded(
              child: Text(t.lastError ?? describeTaskStatus(t, now),
                  style: TextStyle(
                      color: t.lastError != null || t.needsAcknowledgement ? AppColors.danger : AppColors.textMuted, fontSize: 13.5)),
            ),
          ]),
          const SizedBox(height: 12),
          Row(children: [for (var i = 0; i < actions.length; i++) ...[if (i > 0) const SizedBox(width: 10), actions[i]]]),
        ]),
      ),
    );
  }
}
