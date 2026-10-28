import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/discovery/hub_discovery.dart';
import '../../core/pairing/pairing_client.dart';
import '../../core/storage/credential_store.dart';

/// Camcorder Mode pairing: type the 6-digit code shown on the main phone.
/// Main phones on the same Wi-Fi are found automatically; typing an address is
/// only a fallback for networks that block discovery.
class PairingScreen extends StatefulWidget {
  final VoidCallback onPaired;
  final VoidCallback onChangeRole;

  const PairingScreen({super.key, required this.onPaired, required this.onChangeRole});

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  final _codeController = TextEditingController();
  final _addressController = TextEditingController();

  final List<DiscoveredHub> _hubs = [];
  DiscoveredHub? _selected;
  StreamSubscription<DiscoveredHub>? _searchSub;
  bool _isSearching = false;
  bool _showManual = false;
  bool _isBusy = false;
  String? _statusMessage;
  String _deviceId = '';

  @override
  void initState() {
    super.initState();
    _initDevice();
    _search();
    _codeController.addListener(() => setState(() {}));
    _addressController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _searchSub?.cancel();
    _codeController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  Future<void> _initDevice() async {
    final creds = await CredentialStore.load();
    if (mounted) setState(() => _deviceId = creds.deviceId);
  }

  String get _deviceName {
    final suffix = _deviceId.length >= 4 ? _deviceId.substring(_deviceId.length - 4) : _deviceId;
    return 'Camera $suffix';
  }

  void _search() {
    _searchSub?.cancel();
    setState(() {
      _isSearching = true;
      _hubs.clear();
      _selected = null;
    });
    _searchSub = HubDiscovery.discoverHubs().listen(
      (hub) {
        if (!mounted || _hubs.any((h) => h.address == hub.address)) return;
        setState(() {
          _hubs.add(hub);
          _selected ??= hub;
        });
      },
      onDone: () {
        if (mounted) setState(() => _isSearching = false);
      },
    );
  }

  /// Where to send the code: the chosen main phone, a typed address, or every
  /// main phone found (the code is unique to one of them).
  List<HubAddress> get _targets {
    if (_showManual) {
      final typed = HubAddress.tryParse(_addressController.text);
      return typed == null ? [] : [typed];
    }
    if (_selected != null) return [_selected!.address];
    return _hubs.map((h) => h.address).toList();
  }

  bool get _canConnect =>
      !_isBusy && _deviceId.isNotEmpty && _codeController.text.trim().length == 6 && _targets.isNotEmpty;

  Future<void> _connect() async {
    final code = _codeController.text.trim();
    final targets = _targets;
    setState(() {
      _isBusy = true;
      _statusMessage = 'Connecting...';
    });

    PairingResponse? last;
    HubAddress? pairedWith;
    for (final hub in targets) {
      last = await PairingClient.pairWithCode(hub: hub, deviceId: _deviceId, deviceName: _deviceName, code: code);
      if (last.success) {
        pairedWith = hub;
        break;
      }
    }
    if (!mounted) return;

    if (pairedWith != null && last!.deviceToken != null && last.cameraId != null) {
      await CredentialStore.save(
        deviceToken: last.deviceToken!,
        cameraId: last.cameraId!,
        hubIp: pairedWith.host,
        hubPort: pairedWith.port,
      );
      widget.onPaired();
      return;
    }
    setState(() {
      _isBusy = false;
      _statusMessage = last?.errorMessage ?? 'Pairing failed. Check the code and try again.';
    });
  }

  InputDecoration _fieldDecoration(String label) => InputDecoration(
        counterText: '',
        labelText: label,
        labelStyle: const TextStyle(color: Color(0xFF94A3B8)),
        filled: true,
        fillColor: const Color(0xFF1E293B),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
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
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            const Icon(Icons.videocam_outlined, size: 56, color: Color(0xFF38BDF8)),
            const SizedBox(height: 12),
            const Text(
              'Connect to your main phone',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
            ),
            const SizedBox(height: 8),
            const Text(
              'Enter the 6-digit code shown on your main phone (View Mode).',
              textAlign: TextAlign.center,
              style: TextStyle(color: Color(0xFF94A3B8), fontSize: 14),
            ),
            const SizedBox(height: 20),
            TextField(
              controller: _codeController,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              maxLength: 6,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xFFF59E0B), fontSize: 32, letterSpacing: 8, fontWeight: FontWeight.bold),
              decoration: _fieldDecoration('Pairing code'),
            ),
            const SizedBox(height: 20),
            if (!_showManual) ..._nearbySection() else ..._manualSection(),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _canConnect ? _connect : null,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF38BDF8),
                foregroundColor: const Color(0xFF0F172A),
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              child: _isBusy
                  ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5, color: Color(0xFF0F172A)))
                  : const Text('Connect', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            ),
            if (_statusMessage != null) ...[
              const SizedBox(height: 12),
              Text(_statusMessage!, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13)),
            ],
            const SizedBox(height: 24),
            const Text(
              'Not on the same Wi-Fi? Connecting over the internet needs the Smart Spectator relay, which is not set up yet.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Color(0xFF64748B), fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _nearbySection() => [
        Row(children: [
          const Expanded(
            child: Text('MAIN PHONES ON THIS WI-FI',
                style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12, letterSpacing: 1.2, fontWeight: FontWeight.w600)),
          ),
          if (_isSearching)
            const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
          else
            IconButton(
              icon: const Icon(Icons.refresh, color: Color(0xFF38BDF8)),
              tooltip: 'Search again',
              onPressed: _search,
            ),
        ]),
        const SizedBox(height: 8),
        if (_hubs.isEmpty)
          Text(
            _isSearching ? 'Looking for main phones…' : 'No main phone found. Open View Mode on your main phone and keep both phones on the same Wi-Fi.',
            style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
          ),
        ..._hubs.map((hub) {
          final isSelected = hub.address == _selected?.address;
          return Card(
            color: isSelected ? const Color(0xFF1E3A5F) : const Color(0xFF1E293B),
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              onTap: () => setState(() => _selected = hub),
              leading: Icon(isSelected ? Icons.radio_button_checked : Icons.radio_button_off, color: const Color(0xFF38BDF8)),
              title: Text(hub.name, style: const TextStyle(color: Colors.white)),
              subtitle: Text(hub.address.toString(), style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
            ),
          );
        }),
        TextButton(
          onPressed: () => setState(() => _showManual = true),
          child: const Text("Can't see your main phone? Enter its address"),
        ),
      ];

  List<Widget> _manualSection() => [
        TextField(
          controller: _addressController,
          keyboardType: TextInputType.url,
          autocorrect: false,
          style: const TextStyle(color: Colors.white),
          decoration: _fieldDecoration('Main phone address (shown on the main phone)'),
        ),
        if (_addressController.text.isNotEmpty && HubAddress.tryParse(_addressController.text) == null)
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text('Use the form 192.168.1.23 or 192.168.1.23:8000', style: TextStyle(color: Colors.redAccent, fontSize: 12)),
          ),
        TextButton(
          onPressed: () => setState(() => _showManual = false),
          child: const Text('Back to nearby main phones'),
        ),
      ];
}
