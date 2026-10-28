import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../hub/camera_adder.dart';
import '../../hub/device_registry.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';

/// Main phone: add a camera by typing the code shown on the camera phone.
/// Finding the camera on the Wi-Fi and linking it happen automatically.
class AddCameraScreen extends StatefulWidget {
  final DeviceRegistry registry;
  final int hubPort;
  final String hubName;

  const AddCameraScreen({super.key, required this.registry, required this.hubPort, required this.hubName});

  @override
  State<AddCameraScreen> createState() => _AddCameraScreenState();
}

class _AddCameraScreenState extends State<AddCameraScreen> {
  final _code = TextEditingController();
  final _focus = FocusNode();
  bool _busy = false;
  String? _status;
  String? _error;

  @override
  void initState() {
    super.initState();
    _code.addListener(() {
      setState(() {});
      // Six digits typed: connect without needing a button or Enter key.
      if (_code.text.length == 6 && !_busy) _add();
    });
  }

  @override
  void dispose() {
    _code.dispose();
    _focus.dispose();
    super.dispose();
  }

  Future<void> _add() async {
    if (_busy || _code.text.trim().length != 6) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
      _status = 'Looking for the camera on this Wi-Fi…';
    });
    try {
      final name = await CameraAdder.addByCode(
        code: _code.text,
        registry: widget.registry,
        hubPort: widget.hubPort,
        hubName: widget.hubName,
        onStatus: (s) => mounted ? setState(() => _status = s) : null,
      );
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$name added. Tap Start streaming on the camera.')));
      Navigator.of(context).pop(true);
    } on AddCameraError catch (e) {
      if (!mounted) return;
      HapticFeedback.heavyImpact();
      setState(() {
        _busy = false;
        _status = null;
        _error = e.message;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add camera')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(22, 8, 22, 28),
              children: [
                const RingHeader(
                  icon: Icons.add_a_photo_rounded,
                  color: AppColors.ringCameras,
                  progress: 0.5,
                  title: 'Enter the camera code',
                  countRest: 'It is shown on the camera phone',
                ),
                TextField(
                  controller: _code,
                  focusNode: _focus,
                  autofocus: true,
                  enabled: !_busy,
                  keyboardType: TextInputType.number,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _add(),
                  onTapOutside: (_) => FocusScope.of(context).unfocus(),
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.code, fontSize: 38, letterSpacing: 12, fontWeight: FontWeight.w800),
                  decoration: const InputDecoration(counterText: '', hintText: '••••••'),
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: !_busy && _code.text.length == 6 ? _add : null,
                  child: _busy
                      ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5, color: AppColors.onPrimary))
                      : const Text('Add camera'),
                ),
                const SizedBox(height: 14),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 200),
                  child: _error != null
                      ? Text(_error!, key: const ValueKey('e'), textAlign: TextAlign.center, style: const TextStyle(color: AppColors.danger, height: 1.4))
                      : Text(_status ?? '', key: ValueKey(_status), textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textMuted)),
                ),
                const SizedBox(height: 26),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: const [
                      Text('Where is the code?', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                      SizedBox(height: 8),
                      Text(
                        '1. On the camera phone, open VYRO and choose Camera.\n'
                        '2. Its 6-digit code is shown on screen (or tap "Camera code").\n'
                        '3. Type it here — VYRO finds the camera on your Wi-Fi and connects it.',
                        style: TextStyle(color: AppColors.textMuted, height: 1.55),
                      ),
                      SizedBox(height: 8),
                      Text('Both phones must be on the same Wi-Fi. One camera can be added to several main phones.',
                          style: TextStyle(color: AppColors.textFaint, fontSize: 12.5, height: 1.4)),
                    ]),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
