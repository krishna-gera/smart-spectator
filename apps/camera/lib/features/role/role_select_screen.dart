import 'package:flutter/material.dart';

import '../../core/storage/role_store.dart';
import '../../ui/theme.dart';

class RoleSelectScreen extends StatelessWidget {
  final ValueChanged<AppRole> onSelected;

  const RoleSelectScreen({super.key, required this.onSelected});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: ListView(
              shrinkWrap: true,
              padding: const EdgeInsets.all(24),
              children: [
                Container(
                  width: 64,
                  height: 64,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [AppColors.primary, AppColors.ai]),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: const Icon(Icons.visibility_outlined, color: Colors.white, size: 32),
                ),
                const SizedBox(height: 20),
                const Text('Smart Spectator', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800, letterSpacing: -0.5)),
                const SizedBox(height: 8),
                const Text(
                  'Turn spare phones into smart cameras. Video stays on your Wi-Fi.',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 16, height: 1.4),
                ),
                const SizedBox(height: 32),
                const Text('How will this phone be used?', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                const SizedBox(height: 12),
                _RoleCard(
                  icon: Icons.dashboard_outlined,
                  title: 'Main phone',
                  subtitle: 'Watch live feeds, get alerts and AI descriptions, manage cameras.',
                  onTap: () => onSelected(AppRole.viewer),
                ),
                const SizedBox(height: 12),
                _RoleCard(
                  icon: Icons.videocam_outlined,
                  title: 'Camera',
                  subtitle: 'Place this phone where you want to watch. It streams to your main phones.',
                  onTap: () => onSelected(AppRole.camcorder),
                ),
                const SizedBox(height: 16),
                const Text('You can change this later.',
                    textAlign: TextAlign.center, style: TextStyle(color: AppColors.textFaint, fontSize: 13)),
              ],
            ),
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
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: AppColors.primary.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(14)),
              child: Icon(icon, color: AppColors.primary, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text(subtitle, style: const TextStyle(color: AppColors.textMuted, fontSize: 14, height: 1.35)),
              ]),
            ),
            const Icon(Icons.chevron_right, color: AppColors.textFaint),
          ]),
        ),
      ),
    );
  }
}
