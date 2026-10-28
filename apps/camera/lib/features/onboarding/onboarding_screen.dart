import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../ui/theme.dart';
import '../../ui/widgets.dart';

/// First-run guide: three short pages explaining how VYRO works.
class OnboardingScreen extends StatefulWidget {
  final VoidCallback onDone;
  const OnboardingScreen({super.key, required this.onDone});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _pages = PageController();
  int _page = 0;

  static const _steps = [
    (
      Icons.phone_iphone_rounded,
      AppColors.ringCameras,
      'Spare phones become cameras',
      'Put an old phone where you want to watch and choose Camera. It streams straight to your main phone over your Wi-Fi.',
    ),
    (
      Icons.dashboard_rounded,
      AppColors.primary,
      'One main phone sees everything',
      'Your main phone shows live video, motion events and alerts. Pair cameras with a 6-digit code — no IP addresses.',
    ),
    (
      Icons.auto_awesome,
      AppColors.ai,
      'AI watches for you',
      'Describe a job in plain words — "tell me when the washing machine is full" — and VYRO lets you know when it happens.',
    ),
  ];

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  void _next() {
    HapticFeedback.selectionClick();
    if (_page == _steps.length - 1) {
      widget.onDone();
    } else {
      _pages.nextPage(duration: const Duration(milliseconds: 320), curve: Curves.easeOutCubic);
    }
  }

  @override
  Widget build(BuildContext context) {
    final last = _page == _steps.length - 1;
    return Scaffold(
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 8, 0),
            child: Row(children: [
              const VyroLogo(size: 30),
              const SizedBox(width: 10),
              const Text('VYRO', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 3, fontSize: 18)),
              const Spacer(),
              if (!last) TextButton(onPressed: widget.onDone, child: const Text('Skip')),
            ]),
          ),
          Expanded(
            child: PageView.builder(
              controller: _pages,
              itemCount: _steps.length,
              onPageChanged: (i) => setState(() => _page = i),
              itemBuilder: (_, i) {
                final (icon, color, title, body) = _steps[i];
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 28),
                  child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                    i == 0
                        ? const VyroLogo(size: 110, glow: true)
                        : ProgressRing(icon: icon, color: color, progress: (i + 1) / _steps.length, size: 110),
                    const SizedBox(height: 36),
                    Text(title,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: -0.4, height: 1.15)),
                    const SizedBox(height: 14),
                    Text(body, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textMuted, fontSize: 16, height: 1.45)),
                  ]),
                );
              },
            ),
          ),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            for (var i = 0; i < _steps.length; i++)
              AnimatedContainer(
                duration: const Duration(milliseconds: 250),
                margin: const EdgeInsets.symmetric(horizontal: 4),
                width: i == _page ? 22 : 8,
                height: 8,
                decoration: BoxDecoration(
                  color: i == _page ? AppColors.primary : AppColors.surfaceHigh,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
          ]),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 22, 20, 16),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton(onPressed: _next, child: Text(last ? 'Get started' : 'Next')),
            ),
          ),
        ]),
      ),
    );
  }
}
