import 'package:flutter/material.dart';

import '../../hub/hub_server.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import 'camera_card.dart' show describeHealth;

const appVersion = '2.1.0';

/// Main phone settings: cameras, alerts, pairing, web dashboard, about.
class SettingsScreen extends StatefulWidget {
  final List<CameraLink> Function() cameras;
  final String Function() pairingCode;
  final Future<void> Function() onChangeCode;
  final void Function(CameraLink) onCameraSettings;
  final Future<void> Function(CameraLink) onRename;
  final Future<void> Function(CameraLink) onRemove;
  final bool healthAlerts;
  final ValueChanged<bool> onHealthAlerts;
  final String? dashboardAddress;
  final bool aiConfigured;
  final VoidCallback onShowGuide;
  final VoidCallback onChangeRole;

  const SettingsScreen({
    super.key,
    required this.cameras,
    required this.pairingCode,
    required this.onChangeCode,
    required this.onCameraSettings,
    required this.onRename,
    required this.onRemove,
    required this.healthAlerts,
    required this.onHealthAlerts,
    required this.dashboardAddress,
    required this.aiConfigured,
    required this.onShowGuide,
    required this.onChangeRole,
  });

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late bool _healthAlerts = widget.healthAlerts;

  @override
  Widget build(BuildContext context) {
    final cameras = widget.cameras();
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.fromLTRB(18, 0, 18, 28), children: [
          const SectionHeader('Cameras'),
          if (cameras.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(18),
                child: Text('No cameras yet. Use Add camera on the Cameras tab.', style: TextStyle(color: AppColors.textMuted)),
              ),
            )
          else
            Card(
              child: Column(children: [
                for (final c in cameras) ...[
                  if (c != cameras.first) const Divider(height: 1, indent: 16, endIndent: 16),
                  ListTile(
                    leading: Icon(describeHealth(c.health()).$3, color: describeHealth(c.health()).$2),
                    title: Text(c.deviceName),
                    subtitle: Text(describeHealth(c.health()).$1, style: const TextStyle(color: AppColors.textMuted, fontSize: 12.5)),
                    trailing: PopupMenuButton<String>(
                      icon: const Icon(Icons.more_horiz_rounded, color: AppColors.textMuted),
                      onSelected: (v) async {
                        switch (v) {
                          case 'settings':
                            widget.onCameraSettings(c);
                          case 'rename':
                            await widget.onRename(c);
                          case 'remove':
                            await widget.onRemove(c);
                        }
                        if (mounted) setState(() {});
                      },
                      itemBuilder: (_) => const [
                        PopupMenuItem(value: 'settings', child: Text('Motion, alerts & AI')),
                        PopupMenuItem(value: 'rename', child: Text('Rename')),
                        PopupMenuItem(value: 'remove', child: Text('Remove camera')),
                      ],
                    ),
                  ),
                ],
              ]),
            ),
          const SectionHeader('Alerts'),
          Card(
            child: SwitchListTile(
              title: const Text('Camera health alerts'),
              subtitle: const Text('Tell me when a camera\'s battery is low or a streaming camera goes offline.',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 12.5)),
              value: _healthAlerts,
              onChanged: (v) {
                setState(() => _healthAlerts = v);
                widget.onHealthAlerts(v);
              },
            ),
          ),
          const SectionHeader('Web dashboard code'),
          CodeDisplay(
            code: widget.pairingCode(),
            caption: 'Sign in to the web dashboard with this code',
            compact: true,
            onChange: () async {
              await widget.onChangeCode();
              if (mounted) setState(() {});
            },
          ),
          const SectionHeader('Web dashboard'),
          Card(
            child: ListTile(
              leading: const Icon(Icons.language_rounded, color: AppColors.primary),
              title: Text(widget.dashboardAddress != null ? 'http://${widget.dashboardAddress}' : 'Starting…'),
              subtitle: const Text('Open on a computer on the same Wi-Fi and sign in with the code above.',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 12.5)),
            ),
          ),
          const SectionHeader('About'),
          Card(
            child: Column(children: [
              ListTile(
                leading: const VyroLogo(size: 30),
                title: const Text('VYRO', style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: 2)),
                subtitle: const Text('Version $appVersion', style: TextStyle(color: AppColors.textMuted)),
              ),
              const Divider(height: 1, indent: 16, endIndent: 16),
              ListTile(
                leading: Icon(Icons.auto_awesome, color: widget.aiConfigured ? AppColors.ai : AppColors.textFaint),
                title: const Text('AI service'),
                subtitle: Text(widget.aiConfigured ? 'Connected (Groq through the VYRO cloud service)' : 'Not set up in this build',
                    style: const TextStyle(color: AppColors.textMuted, fontSize: 12.5)),
              ),
              const Divider(height: 1, indent: 16, endIndent: 16),
              ListTile(
                leading: const Icon(Icons.menu_book_rounded, color: AppColors.textMuted),
                title: const Text('Show the welcome guide'),
                onTap: widget.onShowGuide,
              ),
              const Divider(height: 1, indent: 16, endIndent: 16),
              ListTile(
                leading: const Icon(Icons.swap_horiz_rounded, color: AppColors.textMuted),
                title: const Text('Use this phone as a camera'),
                onTap: widget.onChangeRole,
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}
