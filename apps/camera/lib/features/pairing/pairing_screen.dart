import 'package:flutter/material.dart';
import '../../core/discovery/hub_discovery.dart';
import '../../core/pairing/pairing_client.dart';
import '../../core/storage/credential_store.dart';

/// Camcorder Mode pairing: (1) ask the main phone for a code, (2) type the
/// code it shows. The two steps are separate so the code the user reads is
/// the one that gets verified.
class PairingScreen extends StatefulWidget {
  final VoidCallback onPaired;
  final VoidCallback onChangeRole;

  const PairingScreen({super.key, required this.onPaired, required this.onChangeRole});

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  final _ipController = TextEditingController();
  final _pinController = TextEditingController();

  bool _isSearching = false;
  bool _isBusy = false;
  bool _codeRequested = false;
  String? _statusMessage;
  int _hubPort = 8000;
  String _deviceId = '';

  @override
  void initState() {
    super.initState();
    _initDevice();
    _startDiscovery();
  }

  @override
  void dispose() {
    _ipController.dispose();
    _pinController.dispose();
    super.dispose();
  }

  Future<void> _initDevice() async {
    final creds = await CredentialStore.load();
    if (!mounted) return;
    setState(() {
      _deviceId = creds.deviceId;
    });
  }

  String get _deviceName {
    final suffix = _deviceId.length >= 4 ? _deviceId.substring(_deviceId.length - 4) : _deviceId;
    return 'Camera $suffix';
  }

  void _startDiscovery() async {
    setState(() {
      _isSearching = true;
      _statusMessage = 'Searching for your main phone on Wi-Fi...';
    });

    String? found;
    await for (final hub in HubDiscovery.discoverHubs()) {
      found = hub.ip;
      if (mounted) {
        setState(() {
          _ipController.text = hub.ip;
          _hubPort = hub.port;
          _statusMessage = 'Found main phone at ${hub.ip}';
        });
      }
      break;
    }

    if (mounted) {
      setState(() {
        _isSearching = false;
        if (found == null) {
          _statusMessage = 'Main phone not found automatically. Type the address shown on the main phone.';
        }
      });
    }
  }

  /// Step 1: create (or reuse) a pairing code on the main phone.
  Future<void> _requestCode() async {
    final hubIp = _ipController.text.trim();
    if (hubIp.isEmpty) {
      setState(() => _statusMessage = 'Enter the main phone address first.');
      return;
    }

    setState(() {
      _isBusy = true;
      _statusMessage = 'Asking the main phone for a pairing code...';
    });

    final result = await PairingClient.requestPairing(
      hubIp: hubIp,
      hubPort: _hubPort,
      deviceId: _deviceId,
      deviceName: _deviceName,
    );

    if (!mounted) return;
    setState(() {
      _isBusy = false;
      _codeRequested = result.success;
      _statusMessage = result.success
          ? 'A 6-digit code is now showing on the main phone. Type it below.'
          : (result.errorMessage ?? 'Could not reach the main phone.');
    });
  }

  /// Step 2: verify the code the user typed.
  Future<void> _verifyCode() async {
    final hubIp = _ipController.text.trim();
    final pin = _pinController.text.trim();
    if (pin.length != 6) {
      setState(() => _statusMessage = 'The code has 6 digits.');
      return;
    }

    setState(() {
      _isBusy = true;
      _statusMessage = 'Pairing...';
    });

    final result = await PairingClient.verifyPairing(
      hubIp: hubIp,
      hubPort: _hubPort,
      deviceId: _deviceId,
      pin: pin,
    );

    if (!mounted) return;
    setState(() => _isBusy = false);

    if (result.success && result.deviceToken != null && result.cameraId != null) {
      await CredentialStore.save(
        deviceToken: result.deviceToken!,
        cameraId: result.cameraId!,
        hubIp: hubIp,
        hubPort: _hubPort,
      );
      widget.onPaired();
    } else {
      setState(() {
        _statusMessage = result.errorMessage ?? 'Pairing failed. Check the code and try again.';
        // The main phone drops the request after too many wrong codes.
        if (_statusMessage!.contains('Request a new code')) _codeRequested = false;
      });
    }
  }

  InputDecoration _fieldDecoration(String label, {Widget? suffix}) => InputDecoration(
        counterText: '',
        labelText: label,
        labelStyle: const TextStyle(color: Color(0xFF94A3B8)),
        filled: true,
        fillColor: const Color(0xFF1E293B),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
        suffixIcon: suffix,
      );

  ButtonStyle get _buttonStyle => ElevatedButton.styleFrom(
        backgroundColor: const Color(0xFF38BDF8),
        foregroundColor: const Color(0xFF0F172A),
        padding: const EdgeInsets.symmetric(vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('Camcorder Mode'),
        backgroundColor: const Color(0xFF1E293B),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.swap_horiz),
            tooltip: 'Change phone mode',
            onPressed: widget.onChangeRole,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(Icons.videocam_outlined, size: 64, color: Color(0xFF38BDF8)),
            const SizedBox(height: 16),
            const Text(
              'Pair with your main phone',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
            ),
            const SizedBox(height: 8),
            const Text(
              'Open Smart Spectator in View Mode on your main phone. Its address is shown at the top of that screen.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Color(0xFF94A3B8), fontSize: 14),
            ),
            const SizedBox(height: 24),
            TextField(
              controller: _ipController,
              enabled: !_codeRequested,
              keyboardType: TextInputType.url,
              style: const TextStyle(color: Colors.white),
              decoration: _fieldDecoration(
                'Main phone address (e.g. 192.168.1.23)',
                suffix: _isSearching
                    ? const Padding(
                        padding: EdgeInsets.all(12.0),
                        child: SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF38BDF8)),
                        ),
                      )
                    : IconButton(
                        icon: const Icon(Icons.refresh, color: Color(0xFF38BDF8)),
                        onPressed: _codeRequested ? null : _startDiscovery,
                      ),
              ),
            ),
            const SizedBox(height: 16),
            if (!_codeRequested)
              ElevatedButton(
                onPressed: _isBusy || _deviceId.isEmpty ? null : _requestCode,
                style: _buttonStyle,
                child: _isBusy
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text('Get pairing code', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              )
            else ...[
              TextField(
                controller: _pinController,
                keyboardType: TextInputType.number,
                maxLength: 6,
                autofocus: true,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFFF59E0B),
                  fontSize: 32,
                  letterSpacing: 8,
                  fontWeight: FontWeight.bold,
                ),
                decoration: _fieldDecoration('Code shown on main phone'),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _isBusy ? null : _verifyCode,
                style: _buttonStyle,
                child: _isBusy
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text('Pair', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ),
              TextButton(
                onPressed: _isBusy ? null : () => setState(() => _codeRequested = false),
                child: const Text('Use a different address'),
              ),
            ],
            if (_statusMessage != null) ...[
              const SizedBox(height: 16),
              Text(
                _statusMessage!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
