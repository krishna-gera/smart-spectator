import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../camera/camcorder_service.dart';
import '../../core/storage/credential_store.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';

/// Camcorder Mode: shows this camera's code and waits. The owner types the
/// code on the main phone (Cameras → Add camera); the main phone finds this
/// camera on the Wi-Fi and links it — nothing to type here.
class PairingScreen extends StatefulWidget {
  final CamcorderService service;
  final VoidCallback onPaired;
  final VoidCallback onChangeRole;

  /// True when this camera already has a main phone and is adding another.
  final bool addingAnother;

  const PairingScreen({
    super.key,
    required this.service,
    required this.onPaired,
    required this.onChangeRole,
    this.addingAnother = false,
  });

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  StreamSubscription<HubLink>? _linkedSub;

  @override
  void initState() {
    super.initState();
    _linkedSub = widget.service.linked.listen((link) {
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(SnackBar(content: Text('Connected to ${link.hubName}')));
      widget.onPaired();
    });
  }

  @override
  void dispose() {
    _linkedSub?.cancel();
    super.dispose();
  }

  Future<void> _changeCode() async {
    if (await confirm(context,
        title: 'Change camera code?',
        message: 'Main phones already connected stay connected. New ones need the new code.',
        action: 'Change')) {
      await widget.service.changeCameraCode();
      if (mounted) setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.addingAnother ? 'Add a main phone' : 'Connect camera'),
        automaticallyImplyLeading: widget.addingAnother,
        actions: [
          if (!widget.addingAnother)
            IconButton(icon: const Icon(Icons.swap_horiz), tooltip: 'Change phone mode', onPressed: widget.onChangeRole),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(22, 8, 22, 28),
              children: [
                const Center(child: VyroLogo(size: 64, glow: true)),
                const SizedBox(height: 18),
                const Text('Enter this code on your main phone',
                    textAlign: TextAlign.center, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, letterSpacing: -0.3)),
                const SizedBox(height: 8),
                const Text(
                  'On the main phone open VYRO → Add camera and type the code. It connects by itself.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.textMuted, height: 1.4),
                ),
                const SizedBox(height: 20),
                CodeDisplay(
                  code: widget.service.cameraCode,
                  caption: '${widget.service.deviceName} · camera code',
                  onChange: _changeCode,
                ),
                const SizedBox(height: 20),
                const Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                  SizedBox(width: 10),
                  Text('Waiting for a main phone…', style: TextStyle(color: AppColors.textMuted)),
                ]),
                const SizedBox(height: 26),
                const Text(
                  'Keep both phones on the same Wi-Fi with VYRO open. The code never changes unless you change it, '
                  'and several main phones can use it.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.textFaint, fontSize: 12.5, height: 1.4),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
