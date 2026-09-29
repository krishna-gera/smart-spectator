import 'package:flutter/material.dart';
import '../../core/discovery/hub_discovery.dart';
import '../../core/pairing/pairing_client.dart';
import '../../core/storage/credential_store.dart';

class PairingScreen extends StatefulWidget {
  final VoidCallback onPaired;

  const PairingScreen({super.key, required this.onPaired});

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  final _ipController = TextEditingController(text: '192.168.1.10');
  final _pinController = TextEditingController();
  
  bool _isSearching = false;
  bool _isPairing = false;
  String? _statusMessage;
  String? _selectedHubIp;
  int _hubPort = 8000;
  String _deviceId = '';

  @override
  void initState() {
    super.initState();
    _initDevice();
    _startDiscovery();
  }

  Future<void> _initDevice() async {
    final creds = await CredentialStore.load();
    setState(() {
      _deviceId = creds.deviceId;
    });
  }

  void _startDiscovery() async {
    setState(() {
      _isSearching = true;
      _statusMessage = 'Searching for Smart Spectator Hub on Wi-Fi...';
    });

    await for (final hub in HubDiscovery.discoverHubs()) {
      if (mounted) {
        setState(() {
          _selectedHubIp = hub.ip;
          _ipController.text = hub.ip;
          _hubPort = hub.port;
          _statusMessage = 'Found ${hub.name} at ${hub.ip}';
        });
        break;
      }
    }

    if (mounted && _selectedHubIp == null) {
      setState(() {
        _isSearching = false;
        _statusMessage = 'Auto-discovery timed out. Enter Hub IP manually below.';
      });
    }
  }

  Future<void> _submitPairing() async {
    final hubIp = _ipController.text.trim();
    final pin = _pinController.text.trim();

    if (hubIp.isEmpty || pin.length != 6) {
      setState(() {
        _statusMessage = 'Please enter a valid 6-digit PIN and Hub IP.';
      });
      return;
    }

    setState(() {
      _isPairing = true;
      _statusMessage = 'Requesting pairing from Hub...';
    });

    // 1. Request pairing first to ensure ephemeral record exists
    await PairingClient.requestPairing(
      hubIp: hubIp,
      hubPort: _hubPort,
      deviceId: _deviceId,
      deviceName: 'Android Camera Node',
    );

    // 2. Verify with entered PIN
    final result = await PairingClient.verifyPairing(
      hubIp: hubIp,
      hubPort: _hubPort,
      deviceId: _deviceId,
      pin: pin,
    );

    setState(() {
      _isPairing = false;
    });

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
        _statusMessage = result.errorMessage ?? 'Pairing failed. Check PIN and try again.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('Smart Spectator Camera'),
        backgroundColor: const Color(0xFF1E293B),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(
              Icons.videocam_outlined,
              size: 64,
              color: Color(0xFF38BDF8),
            ),
            const SizedBox(height: 16),
            const Text(
              'Pair Camera with Hub',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Check your Desktop Hub screen for the 6-digit verification code.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Color(0xFF94A3B8), fontSize: 14),
            ),
            const SizedBox(height: 24),
            
            // Hub IP Input
            TextField(
              controller: _ipController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                labelText: 'Hub LAN IP Address',
                labelStyle: const TextStyle(color: Color(0xFF94A3B8)),
                filled: true,
                fillColor: const Color(0xFF1E293B),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                suffixIcon: _isSearching
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
                        onPressed: _startDiscovery,
                      ),
              ),
            ),
            const SizedBox(height: 16),

            // 6-digit PIN input
            TextField(
              controller: _pinController,
              keyboardType: TextInputType.number,
              maxLength: 6,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Color(0xFFF59E0B),
                fontSize: 32,
                letterSpacing: 8,
                fontWeight: FontWeight.bold,
              ),
              decoration: InputDecoration(
                counterText: '',
                labelText: 'Enter 6-Digit PIN',
                labelStyle: const TextStyle(color: Color(0xFF94A3B8), fontSize: 16),
                filled: true,
                fillColor: const Color(0xFF1E293B),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
            const SizedBox(height: 24),

            ElevatedButton(
              onPressed: _isPairing ? null : _submitPairing,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF38BDF8),
                foregroundColor: const Color(0xFF0F172A),
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              child: _isPairing
                  ? const CircularProgressIndicator(color: Colors.white)
                  : const Text('Pair & Connect', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            ),

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
