import 'package:flutter/material.dart';
import '../../core/storage/role_store.dart';

class RoleSelectScreen extends StatelessWidget {
  final ValueChanged<AppRole> onSelected;

  const RoleSelectScreen({super.key, required this.onSelected});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('Smart Spectator'),
        backgroundColor: const Color(0xFF1E293B),
        elevation: 0,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'How will this phone be used?',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
              ),
              const SizedBox(height: 8),
              const Text(
                'You can change this later.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Color(0xFF94A3B8)),
              ),
              const SizedBox(height: 32),
              _RoleCard(
                icon: Icons.monitor_heart_outlined,
                title: 'View Mode — Main phone',
                subtitle: 'Pair camera phones, watch live feeds, get alerts.',
                onTap: () => onSelected(AppRole.viewer),
              ),
              const SizedBox(height: 16),
              _RoleCard(
                icon: Icons.videocam_outlined,
                title: 'Camcorder Mode — Camera phone',
                subtitle: 'Turn this phone into a camera that streams to your main phone.',
                onTap: () => onSelected(AppRole.camcorder),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RoleCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _RoleCard({required this.icon, required this.title, required this.subtitle, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: const Color(0xFF1E293B),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Icon(icon, size: 40, color: const Color(0xFF38BDF8)),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 4),
                    Text(subtitle, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
