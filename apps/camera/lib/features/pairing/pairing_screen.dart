import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../camera/camcorder_service.dart';
import '../../core/discovery/hub_discovery.dart';
import '../../core/pairing/pairing_client.dart';
import '../../core/storage/credential_store.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';

/// Camcorder Mode: connect this camera to a main phone. Two ways:
///  1. type the main phone's code here, or
///  2. on the main phone choose "Add camera" and type this camera's code.
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
  final _codeController = TextEditingController();
  final _addressController = TextEditingController();

  final List<DiscoveredHub> _hubs = [];
  DiscoveredHub? _selected;
  StreamSubscription<DiscoveredHub>? _searchSub;
  StreamSubscription<HubLink>? _linkedSub;
  bool _searching = false;
  bool _showManual = false;
  bool _busy = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _search();
    _codeController.addListener(() => setState(() {}));
    _addressController.addListener(() => setState(() {}));
    // A main phone added this camera by the camera's code.
    _linkedSub = widget.service.linked.listen((_) {
      if (mounted) widget.onPaired();
    });
  }

  @override
  void dispose() {
    _searchSub?.cancel();
    _linkedSub?.cancel();
    _codeController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  void _search() {
    _searchSub?.cancel();
    setState(() {
      _searching = true;
      _hubs.clear();
      _selected = null;
    });
    final known = widget.service.hubs.map((h) => h.key).toSet();
    _searchSub = HubDiscovery.discoverHubs().listen(
      (hub) {
        if (!mounted || _hubs.any((h) => h.address == hub.address)) return;
        if (known.contains('${hub.address.host}:${hub.address.port}')) return; // already connected
        setState(() {
          _hubs.add(hub);
          _selected ??= hub;
        });
      },
      onDone: () {
        if (mounted) setState(() => _searching = false);
      },
    );
  }

  List<(HubAddress, String)> get _targets {
    if (_showManual) {
      final typed = HubAddress.tryParse(_addressController.text);
      return typed == null ? [] : [(typed, 'Main phone')];
    }
    if (_selected != null) return [(_selected!.address, _selected!.name)];
    return _hubs.map((h) => (h.address, h.name)).toList();
  }

  bool get _canConnect => !_busy && _codeController.text.trim().length == 6 && _targets.isNotEmpty;

  Future<void> _connect() async {
    final creds = widget.service.credentials;
    if (creds == null) return;
    setState(() {
      _busy = true;
      _message = 'Connecting…';
    });
    PairingResponse? last;
    for (final (address, name) in _targets) {
      last = await PairingClient.pairWithCode(
        hub: address,
        deviceId: creds.deviceId,
        deviceName: widget.service.deviceName,
        code: _codeController.text,
      );
      if (last.success && last.deviceToken != null && last.cameraId != null) {
        await CredentialStore.addHub(HubLink(
          hubHost: address.host,
          hubPort: address.port,
          hubName: name,
          cameraId: last.cameraId!,
          deviceToken: last.deviceToken!,
        ));
        await widget.service.reload();
        if (mounted) widget.onPaired();
        return;
      }
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      _message = last?.errorMessage ?? 'Could not connect. Check the code and try again.';
    });
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
            constraints: const BoxConstraints(maxWidth: 560),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
              children: [
                const Text('Enter the main phone\'s code',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, letterSpacing: -0.3)),
                const SizedBox(height: 6),
                const Text(
                  'Open VYRO on your main phone. Its pairing code is on the Cameras screen.',
                  style: TextStyle(color: AppColors.textMuted, height: 1.4),
                ),
                const SizedBox(height: 18),
                TextField(
                  controller: _codeController,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  maxLength: 6,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.code, fontSize: 34, letterSpacing: 10, fontWeight: FontWeight.w800),
                  decoration: const InputDecoration(counterText: '', hintText: '••••••'),
                ),
                if (!_showManual) ..._nearby() else ..._manual(),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _canConnect ? _connect : null,
                  child: _busy
                      ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white))
                      : const Text('Connect'),
                ),
                if (_message != null) ...[
                  const SizedBox(height: 12),
                  Text(_message!, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textMuted)),
                ],
                const SectionHeader('Or add this camera from the main phone'),
                CodeDisplay(
                  code: widget.service.cameraCode,
                  caption: 'On the main phone: Cameras → Add camera → ${widget.service.deviceName}',
                  compact: true,
                ),
                const SizedBox(height: 18),
                const Text(
                  'Both phones need to be on the same Wi-Fi. Connecting over the internet needs the VYRO relay, '
                  'which is not set up yet.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.textFaint, fontSize: 12, height: 1.4),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _nearby() => [
        SectionHeader(
          'Main phones on this Wi-Fi',
          trailing: _searching
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : IconButton(
                  icon: const Icon(Icons.refresh, size: 20, color: AppColors.primary),
                  tooltip: 'Search again',
                  visualDensity: VisualDensity.compact,
                  onPressed: _search,
                ),
        ),
        if (_hubs.isEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                _searching ? 'Looking for main phones…' : 'None found. Make sure the main phone has VYRO open.',
                style: const TextStyle(color: AppColors.textMuted),
              ),
            ),
          ),
        for (final hub in _hubs)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Card(
              color: hub.address == _selected?.address ? AppColors.primary.withValues(alpha: 0.12) : null,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
                side: BorderSide(color: hub.address == _selected?.address ? AppColors.primary : AppColors.border),
              ),
              child: ListTile(
                onTap: () => setState(() => _selected = hub),
                leading: Icon(
                  hub.address == _selected?.address ? Icons.radio_button_checked : Icons.radio_button_off,
                  color: AppColors.primary,
                ),
                title: Text(hub.name),
                subtitle: Text(hub.address.toString(), style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
              ),
            ),
          ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(
            onPressed: () => setState(() => _showManual = true),
            child: const Text("Can't see it? Enter the main phone's address"),
          ),
        ),
      ];

  List<Widget> _manual() => [
        const SizedBox(height: 16),
        TextField(
          controller: _addressController,
          keyboardType: TextInputType.url,
          autocorrect: false,
          decoration: const InputDecoration(labelText: 'Main phone address', hintText: '192.168.1.23'),
        ),
        if (_addressController.text.isNotEmpty && HubAddress.tryParse(_addressController.text) == null)
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text('Use the form 192.168.1.23 or 192.168.1.23:8000', style: TextStyle(color: AppColors.danger, fontSize: 12)),
          ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(
            onPressed: () => setState(() => _showManual = false),
            child: const Text('Back to nearby main phones'),
          ),
        ),
      ];
}
