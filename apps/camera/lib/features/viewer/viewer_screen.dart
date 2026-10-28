import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/platform/system_bridge.dart';
import '../../core/video/live_video_controller.dart';
import '../../hub/device_registry.dart';
import '../../hub/hub_server.dart';

/// Main phone (View Mode): runs the local hub and shows paired cameras.
class ViewerScreen extends StatefulWidget {
  final VoidCallback onChangeRole;

  const ViewerScreen({super.key, required this.onChangeRole});

  @override
  State<ViewerScreen> createState() => _ViewerScreenState();
}

class _ViewerScreenState extends State<ViewerScreen> {
  late final DeviceRegistry _registry = DeviceRegistry(store: SharedPrefsDeviceStore());
  late final HubServer _server = HubServer(registry: _registry);
  final Map<String, LiveVideoController> _live = {};
  StreamSubscription<void>? _changesSub;
  Timer? _ticker;
  String? _localIp;
  String? _error;

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    try {
      await _registry.load();
      await _server.start();
      _localIp = await HubServer.localIpAddress();
      // Keep receiving with the screen off, and let camera phones find us.
      await SystemBridge.startHubService(text: 'Main phone hub at ${_localIp ?? 'this phone'}:${_server.boundPort}');
      _server.displayName = 'Main phone${_localIp != null ? ' ($_localIp)' : ''}';
      await SystemBridge.advertiseHub(_server.boundPort!, _server.displayName);
      _changesSub = _server.changes.listen((_) {
        _syncLiveVideo();
        if (mounted) setState(() {});
      });
      _syncLiveVideo();
      // Refresh PIN countdowns and stale stream indicators.
      _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) setState(() {});
      });
    } catch (e) {
      _error = 'Could not start the local hub on port ${HubServer.defaultPort}: $e';
    }
    if (mounted) setState(() {});
  }

  /// One decoder per streaming camera; released when the camera stops.
  void _syncLiveVideo() {
    final streaming = {for (final c in _server.cameras.where((c) => c.streaming)) c.cameraId};
    for (final id in _live.keys.where((id) => !streaming.contains(id)).toList()) {
      _live.remove(id)!.dispose();
    }
    for (final id in streaming.where((id) => !_live.containsKey(id))) {
      final controller = LiveVideoController(
        cameraId: id,
        packets: _server.packets,
        requestKeyframe: _server.requestKeyframe,
      );
      _live[id] = controller;
      controller.start();
    }
  }

  void _openFullScreen(CameraLink cam, LiveVideoController controller) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => _FullScreenView(camera: cam, controller: controller),
    ));
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

  Future<void> _confirmRevoke(CameraLink cam) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove camera?'),
        content: Text('${cam.deviceName} will be disconnected and must pair again.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Remove')),
        ],
      ),
    );
    if (ok == true) await _server.revokeDevice(cam.deviceId);
  }

  @override
  Widget build(BuildContext context) {
    final pending = _registry.pendingPairings;
    final cameras = _server.cameras;

    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('Smart Spectator — Main Phone'),
        backgroundColor: const Color(0xFF1E293B),
        actions: [
          IconButton(
            icon: const Icon(Icons.swap_horiz),
            tooltip: 'Change phone mode',
            onPressed: widget.onChangeRole,
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _HubStatusCard(running: _server.isRunning, ip: _localIp, port: _server.boundPort, error: _error),
          if (_server.isRunning) ...[
            const SizedBox(height: 16),
            _PairingCodeCard(code: _registry.hubCode, expiresAt: _registry.hubCodeExpiresAt, onNewCode: () {
              setState(_registry.rotateHubCode);
            }),
          ],
          const SizedBox(height: 16),
          if (pending.isNotEmpty) ...[
            const _SectionTitle('Pairing requests'),
            ...pending.map((p) => _PinCard(pending: p)),
            const SizedBox(height: 16),
          ],
          if (_live.isNotEmpty) ...[
            const _SectionTitle('Live'),
            GridView.count(
              crossAxisCount: _live.length == 1 ? 1 : 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: _live.length == 1 ? 16 / 10 : 1,
              children: [
                for (final cam in cameras.where((c) => _live.containsKey(c.cameraId)))
                  GestureDetector(
                    onTap: () => _openFullScreen(cam, _live[cam.cameraId]!),
                    child: _LiveTile(camera: cam, controller: _live[cam.cameraId]!),
                  ),
              ],
            ),
            const SizedBox(height: 16),
          ],
          _SectionTitle('Cameras (${cameras.length})'),
          if (cameras.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text(
                'No cameras yet. On another phone choose Camcorder Mode and enter the pairing code above.',
                style: TextStyle(color: Color(0xFF94A3B8)),
              ),
            ),
          ...cameras.map((c) => _CameraCard(camera: c, onRemove: () => _confirmRevoke(c))),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;
  const _SectionTitle(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(text.toUpperCase(),
            style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12, letterSpacing: 1.2, fontWeight: FontWeight.w600)),
      );
}

class _HubStatusCard extends StatelessWidget {
  final bool running;
  final String? ip;
  final int? port;
  final String? error;

  const _HubStatusCard({required this.running, required this.ip, required this.port, required this.error});

  @override
  Widget build(BuildContext context) {
    final address = ip != null && port != null ? '$ip:$port' : 'finding address…';
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: const Color(0xFF1E293B), borderRadius: BorderRadius.circular(12)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(Icons.circle, size: 10, color: running ? Colors.greenAccent : Colors.redAccent),
            const SizedBox(width: 8),
            Text(running ? 'Local hub running' : 'Local hub stopped',
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          ]),
          const SizedBox(height: 8),
          const SizedBox(height: 4),
          const Text('Keep this app open while cameras are streaming. Camera phones on the same Wi-Fi find this phone automatically.',
              style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
          const SizedBox(height: 4),
          Text('Address (only if a camera can\'t find this phone): $address',
              style: const TextStyle(color: Color(0xFF64748B), fontSize: 12)),
          if (error != null) ...[
            const SizedBox(height: 8),
            Text(error!, style: const TextStyle(color: Colors.redAccent, fontSize: 12)),
          ],
        ],
      ),
    );
  }
}

class _PinCard extends StatelessWidget {
  final PendingPairing pending;
  const _PinCard({required this.pending});

  @override
  Widget build(BuildContext context) {
    final secondsLeft = pending.expiresAt.difference(DateTime.now()).inSeconds.clamp(0, 9999);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF090D16),
        border: Border.all(color: const Color(0xFFF59E0B)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(children: [
        Text(pending.deviceName, style: const TextStyle(color: Color(0xFF94A3B8))),
        const SizedBox(height: 4),
        Text(pending.pin,
            style: const TextStyle(color: Color(0xFFF59E0B), fontSize: 34, letterSpacing: 8, fontWeight: FontWeight.bold)),
        Text('Type this code on the camera phone · expires in ${secondsLeft}s',
            style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
      ]),
    );
  }
}

class _CameraCard extends StatelessWidget {
  final CameraLink camera;
  final VoidCallback onRemove;
  const _CameraCard({required this.camera, required this.onRemove});

  @override
  Widget build(BuildContext context) {
    final last = camera.lastPacketAt;
    final live = camera.streaming && last != null && DateTime.now().difference(last).inSeconds < 3;
    final status = live
        ? 'Streaming'
        : camera.streaming
            ? 'Connected, no video'
            : camera.controlConnected
                ? 'Online, not streaming'
                : 'Offline';
    final color = live ? Colors.greenAccent : (camera.controlConnected ? Colors.amberAccent : Colors.redAccent);
    final battery = camera.batteryLevel != null
        ? '${camera.batteryLevel!.round()}%${camera.isCharging == true ? ' ⚡' : ''}'
        : '—';

    return Card(
      color: const Color(0xFF1E293B),
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(Icons.videocam, color: color),
        title: Text(camera.deviceName, style: const TextStyle(color: Colors.white)),
        subtitle: Text(
          '$status · battery $battery\n'
          '${camera.fps.toStringAsFixed(1)} pkt/s · ${camera.bitrateKbps.toStringAsFixed(0)} kbps · '
          '${camera.packetsReceived} pkts · ${camera.droppedPackets} dropped',
          style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
        ),
        isThreeLine: true,
        trailing: IconButton(
          icon: const Icon(Icons.link_off, color: Colors.redAccent),
          tooltip: 'Remove camera',
          onPressed: onRemove,
        ),
      ),
    );
  }
}

/// Decoded video for one camera, rotated upright and letterboxed.
class _LiveVideo extends StatelessWidget {
  final CameraLink camera;
  final LiveVideoController controller;
  const _LiveVideo({required this.camera, required this.controller});

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
          return const _VideoMessage('Waiting for picture…', spinner: true);
        }
        final quarterTurns = camera.rotationDegrees ~/ 90;
        final sideways = quarterTurns.isOdd;
        final aspect = sideways ? 1 / controller.aspectRatio : controller.aspectRatio;
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
          Text(text, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
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
      borderRadius: BorderRadius.circular(12),
      child: Container(
        color: Colors.black,
        child: Stack(fit: StackFit.expand, children: [
          _LiveVideo(camera: camera, controller: controller),
          Positioned(
            left: 8,
            top: 8,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(6)),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.circle, size: 8, color: Colors.redAccent),
                const SizedBox(width: 6),
                Text(camera.deviceName, style: const TextStyle(color: Colors.white, fontSize: 12)),
              ]),
            ),
          ),
        ]),
      ),
    );
  }
}

class _FullScreenView extends StatelessWidget {
  final CameraLink camera;
  final LiveVideoController controller;
  const _FullScreenView({required this.camera, required this.controller});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        title: Text(camera.deviceName),
      ),
      body: SafeArea(child: _LiveVideo(camera: camera, controller: controller)),
    );
  }
}

/// The code camera phones type to connect; rotates every few minutes.
class _PairingCodeCard extends StatelessWidget {
  final String code;
  final DateTime expiresAt;
  final VoidCallback onNewCode;
  const _PairingCodeCard({required this.code, required this.expiresAt, required this.onNewCode});

  @override
  Widget build(BuildContext context) {
    final left = expiresAt.difference(DateTime.now());
    final mm = left.inMinutes.clamp(0, 99);
    final ss = (left.inSeconds % 60).clamp(0, 59).toString().padLeft(2, '0');
    final spaced = '${code.substring(0, 3)} ${code.substring(3)}';
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF090D16),
        border: Border.all(color: const Color(0xFFF59E0B)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(children: [
        const Text('PAIRING CODE', style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12, letterSpacing: 1.2)),
        const SizedBox(height: 6),
        Text(spaced,
            style: const TextStyle(color: Color(0xFFF59E0B), fontSize: 40, letterSpacing: 6, fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        Text('On a camera phone: Camcorder Mode → enter this code · new code in $mm:$ss',
            textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
        TextButton(onPressed: onNewCode, child: const Text('Show a new code')),
      ]),
    );
  }
}
