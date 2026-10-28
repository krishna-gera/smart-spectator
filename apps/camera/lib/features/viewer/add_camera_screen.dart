import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../hub/camera_adder.dart';
import '../../hub/device_registry.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';

/// Main phone: add a camera phone by the code shown on that camera.
class AddCameraScreen extends StatefulWidget {
  final DeviceRegistry registry;
  final int hubPort;
  final String hubName;
  final String hubCode;

  const AddCameraScreen({
    super.key,
    required this.registry,
    required this.hubPort,
    required this.hubName,
    required this.hubCode,
  });

  @override
  State<AddCameraScreen> createState() => _AddCameraScreenState();
}

class _AddCameraScreenState extends State<AddCameraScreen> {
  final _code = TextEditingController();
  final List<DiscoveredCamera> _cameras = [];
  DiscoveredCamera? _selected;
  StreamSubscription<DiscoveredCamera>? _sub;
  bool _searching = false;
  bool _busy = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _code.addListener(() => setState(() {}));
    _search();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _code.dispose();
    super.dispose();
  }

  void _search() {
    _sub?.cancel();
    final known = widget.registry.devices.where((d) => !d.revoked).map((d) => d.deviceId).toSet();
    setState(() {
      _searching = true;
      _cameras.clear();
      _selected = null;
    });
    _sub = CameraAdder.discover().listen(
      (cam) {
        if (!mounted || known.contains(cam.deviceId)) return;
        setState(() {
          _cameras.add(cam);
          _selected ??= cam;
        });
      },
      onDone: () {
        if (mounted) setState(() => _searching = false);
      },
    );
  }

  Future<void> _add() async {
    final cam = _selected;
    if (cam == null) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    final error = await CameraAdder.add(
      camera: cam,
      code: _code.text,
      registry: widget.registry,
      hubPort: widget.hubPort,
      hubName: widget.hubName,
    );
    if (!mounted) return;
    if (error == null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${cam.name} added. Start streaming on the camera.')));
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _busy = false;
      _message = error;
    });
  }

  @override
  Widget build(BuildContext context) {
    final canAdd = !_busy && _selected != null && _code.text.trim().length == 6;
    return Scaffold(
      appBar: AppBar(title: const Text('Add camera')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
              children: [
                const Text('Pick a camera and enter its code',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, letterSpacing: -0.3)),
                const SizedBox(height: 6),
                const Text(
                  'On the camera phone, open VYRO as Camera and tap "Camera code". '
                  'The same camera can be added to several main phones.',
                  style: TextStyle(color: AppColors.textMuted, height: 1.4),
                ),
                SectionHeader(
                  'Cameras on this Wi-Fi',
                  trailing: _searching
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : IconButton(
                          icon: const Icon(Icons.refresh, size: 20, color: AppColors.primary),
                          visualDensity: VisualDensity.compact,
                          tooltip: 'Search again',
                          onPressed: _search,
                        ),
                ),
                if (_cameras.isEmpty)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(
                        _searching
                            ? 'Looking for camera phones…'
                            : 'No new cameras found. Open VYRO as Camera on the other phone, on the same Wi-Fi.',
                        style: const TextStyle(color: AppColors.textMuted),
                      ),
                    ),
                  ),
                for (final cam in _cameras)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Card(
                      color: cam.deviceId == _selected?.deviceId ? AppColors.primary.withValues(alpha: 0.12) : null,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                        side: BorderSide(color: cam.deviceId == _selected?.deviceId ? AppColors.primary : AppColors.border),
                      ),
                      child: ListTile(
                        onTap: () => setState(() => _selected = cam),
                        leading: const Icon(Icons.videocam_outlined, color: AppColors.primary),
                        title: Text(cam.name),
                        subtitle: Text(cam.address.host, style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
                        trailing: cam.deviceId == _selected?.deviceId ? const Icon(Icons.check_circle, color: AppColors.primary) : null,
                      ),
                    ),
                  ),
                const SizedBox(height: 12),
                TextField(
                  controller: _code,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  maxLength: 6,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.code, fontSize: 34, letterSpacing: 10, fontWeight: FontWeight.w800),
                  decoration: const InputDecoration(counterText: '', hintText: 'Camera code'),
                ),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: canAdd ? _add : null,
                  child: _busy
                      ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white))
                      : const Text('Add camera'),
                ),
                if (_message != null) ...[
                  const SizedBox(height: 12),
                  Text(_message!, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.danger)),
                ],
                const SectionHeader('Or, on the camera phone'),
                CodeDisplay(code: widget.hubCode, caption: 'Enter this main phone\'s code on the camera', compact: true),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
