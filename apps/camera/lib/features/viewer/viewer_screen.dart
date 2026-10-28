import 'dart:async';
import 'package:flutter/material.dart';
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
      _changesSub = _server.changes.listen((_) {
        if (mounted) setState(() {});
      });
      // Refresh PIN countdowns and stale stream indicators.
      _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) setState(() {});
      });
    } catch (e) {
      _error = 'Could not start the local hub on port ${HubServer.defaultPort}: $e';
    }
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _changesSub?.cancel();
    _server.dispose();
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
          const SizedBox(height: 16),
          if (pending.isNotEmpty) ...[
            const _SectionTitle('Pairing requests'),
            ...pending.map((p) => _PinCard(pending: p)),
            const SizedBox(height: 16),
          ],
          _SectionTitle('Cameras (${cameras.length})'),
          if (cameras.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text(
                'No cameras yet. On another phone choose Camcorder Mode, enter the address above, and tap "Get pairing code".',
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
          Text('Camera phones connect to: $address', style: const TextStyle(color: Color(0xFF38BDF8), fontSize: 16)),
          const SizedBox(height: 4),
          const Text('Keep this app open while cameras are streaming. Both phones must be on the same Wi-Fi.',
              style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
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
