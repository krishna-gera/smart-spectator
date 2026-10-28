import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'theme.dart';

/// Header from the design language: an icon inside a coloured progress ring,
/// a large bold title and a small counter line ("2/3 cameras live").
class RingHeader extends StatelessWidget {
  final IconData icon;
  final Color color;

  /// 0–1; how much of the ring is filled.
  final double progress;
  final String title;
  final String? countStrong;
  final String? countRest;

  const RingHeader({
    super.key,
    required this.icon,
    required this.color,
    required this.progress,
    required this.title,
    this.countStrong,
    this.countRest,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
      child: Column(children: [
        SizedBox(
          width: 76,
          height: 76,
          child: CustomPaint(
            painter: _RingPainter(color: color, progress: progress.clamp(0.0, 1.0)),
            child: Center(
              child: Container(
                width: 50,
                height: 50,
                decoration: const BoxDecoration(color: AppColors.surfaceHigh, shape: BoxShape.circle),
                child: Icon(icon, color: Colors.white, size: 26),
              ),
            ),
          ),
        ),
        const SizedBox(height: 14),
        Text(title, textAlign: TextAlign.center, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: -0.4)),
        if (countStrong != null || countRest != null) ...[
          const SizedBox(height: 4),
          Text.rich(
            TextSpan(children: [
              if (countStrong != null) TextSpan(text: countStrong, style: const TextStyle(fontWeight: FontWeight.w800, color: AppColors.text)),
              if (countRest != null) TextSpan(text: ' $countRest'),
            ]),
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.textMuted, fontSize: 15),
          ),
        ],
      ]),
    );
  }
}

/// Small icon-in-ring indicator (same look as [RingHeader]) for list items.
class ProgressRing extends StatelessWidget {
  final IconData icon;
  final Color color;
  final double progress;
  final double size;
  const ProgressRing({super.key, required this.icon, required this.color, required this.progress, this.size = 48});

  @override
  Widget build(BuildContext context) => SizedBox(
        width: size,
        height: size,
        child: CustomPaint(
          painter: _RingPainter(color: color, progress: progress.clamp(0.0, 1.0), stroke: size / 12),
          child: Center(child: Icon(icon, color: Colors.white, size: size * 0.42)),
        ),
      );
}

class _RingPainter extends CustomPainter {
  final Color color;
  final double progress;
  final double stroke;
  _RingPainter({required this.color, required this.progress, this.stroke = 6});

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final arcRect = rect.deflate(stroke / 2);
    canvas.drawArc(arcRect, 0, math.pi * 2, false,
        Paint()
          ..color = color.withValues(alpha: 0.22)
          ..style = PaintingStyle.stroke
          ..strokeWidth = stroke);
    if (progress > 0) {
      canvas.drawArc(arcRect, -math.pi / 2, math.pi * 2 * progress, false,
          Paint()
            ..color = color
            ..style = PaintingStyle.stroke
            ..strokeCap = StrokeCap.round
            ..strokeWidth = stroke);
    }
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.color != color || old.progress != progress;
}

/// Bold yellow call-to-action card with a dark round icon on the right.
class ActionBanner extends StatelessWidget {
  final String title;
  final String? subtitle;
  final IconData icon;
  final VoidCallback? onTap;
  final bool compact;

  const ActionBanner({super.key, required this.title, this.subtitle, required this.icon, this.onTap, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null;
    return Material(
      color: enabled ? AppColors.primary : AppColors.surfaceHigh,
      borderRadius: BorderRadius.circular(AppTheme.radius),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppTheme.radius),
        onTap: onTap,
        child: Padding(
          padding: EdgeInsets.fromLTRB(20, compact ? 14 : 18, 14, compact ? 14 : 18),
          child: Row(children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                Text(title,
                    style: TextStyle(
                        color: enabled ? AppColors.onPrimary : AppColors.textFaint,
                        fontSize: compact ? 17 : 19,
                        fontWeight: FontWeight.w800)),
                if (subtitle != null) ...[
                  const SizedBox(height: 4),
                  Text(subtitle!,
                      style: TextStyle(color: enabled ? AppColors.onPrimary.withValues(alpha: 0.75) : AppColors.textFaint, fontSize: 13.5)),
                ],
              ]),
            ),
            const SizedBox(width: 12),
            Container(
              width: compact ? 38 : 46,
              height: compact ? 38 : 46,
              decoration: BoxDecoration(color: enabled ? AppColors.onPrimary : AppColors.surface, shape: BoxShape.circle),
              child: Icon(icon, color: enabled ? Colors.white : AppColors.textFaint, size: compact ? 20 : 24),
            ),
          ]),
        ),
      ),
    );
  }
}

/// White filled circle with a dark check (done/on) or a grey outline (not).
class CheckCircle extends StatelessWidget {
  final bool checked;
  final double size;
  const CheckCircle({super.key, required this.checked, this.size = 30});

  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: checked ? Colors.white : Colors.transparent,
          shape: BoxShape.circle,
          border: checked ? null : Border.all(color: AppColors.textFaint, width: 1.6),
        ),
        child: checked ? Icon(Icons.check_rounded, size: size * 0.62, color: AppColors.onPrimary) : null,
      );
}

/// Centred group label with a small icon ("☀ Today").
class CenteredLabel extends StatelessWidget {
  final String text;
  final IconData icon;
  final Color iconColor;
  const CenteredLabel(this.text, {super.key, required this.icon, this.iconColor = AppColors.primary});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 18, 4, 12),
        child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          Icon(icon, size: 20, color: iconColor),
          const SizedBox(width: 8),
          Text(text, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        ]),
      );
}

/// Small heading above a group of content.
class SectionHeader extends StatelessWidget {
  final String text;
  final Widget? trailing;
  const SectionHeader(this.text, {super.key, this.trailing});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(6, 22, 4, 10),
        child: Row(children: [
          Expanded(child: Text(text, style: const TextStyle(color: AppColors.text, fontSize: 17, fontWeight: FontWeight.w700))),
          ?trailing,
        ]),
      );
}

/// Coloured dot + label, e.g. "LIVE", "Online", "Motion".
class StatusChip extends StatelessWidget {
  final String label;
  final Color color;
  final bool filled;
  final IconData? icon;
  const StatusChip(this.label, {super.key, required this.color, this.filled = false, this.icon});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: filled ? color : color.withValues(alpha: 0.16),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (icon != null)
            Icon(icon, size: 13, color: filled ? AppColors.onPrimary : color)
          else
            Container(
                width: 7, height: 7, decoration: BoxDecoration(color: filled ? AppColors.onPrimary : color, shape: BoxShape.circle)),
          const SizedBox(width: 6),
          Text(label,
              style: TextStyle(
                  color: filled ? AppColors.onPrimary : color, fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 0.2)),
        ]),
      );
}

/// A 6-digit pairing code shown large, with copy.
class CodeDisplay extends StatelessWidget {
  final String code;
  final String caption;
  final VoidCallback? onChange;
  final bool compact;

  const CodeDisplay({super.key, required this.code, required this.caption, this.onChange, this.compact = false});

  String get _spaced => code.length == 6 ? '${code.substring(0, 3)} ${code.substring(3)}' : code;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: EdgeInsets.all(compact ? 16 : 22),
        child: Column(children: [
          Text(caption, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textMuted, fontSize: 13.5)),
          const SizedBox(height: 10),
          InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: () {
              Clipboard.setData(ClipboardData(text: code));
              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Code copied')));
            },
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
              child: Text(_spaced,
                  style: TextStyle(
                      color: AppColors.code,
                      fontSize: compact ? 32 : 44,
                      letterSpacing: compact ? 4 : 6,
                      fontWeight: FontWeight.w800,
                      fontFeatures: const [FontFeature.tabularFigures()])),
            ),
          ),
          if (onChange != null) ...[
            const SizedBox(height: 4),
            TextButton.icon(
              onPressed: onChange,
              icon: const Icon(Icons.refresh_rounded, size: 18),
              label: const Text('Change code'),
              style: TextButton.styleFrom(foregroundColor: AppColors.textMuted),
            ),
          ],
        ]),
      ),
    );
  }
}

/// Centered icon + title + explanation for empty screens.
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;
  final Widget? action;
  const EmptyState({super.key, required this.icon, required this.title, required this.message, this.action});

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: const BoxDecoration(color: AppColors.surface, shape: BoxShape.circle),
              child: Icon(icon, size: 32, color: AppColors.primary),
            ),
            const SizedBox(height: 16),
            Text(title, textAlign: TextAlign.center, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text(message, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textMuted, height: 1.4)),
            if (action != null) ...[const SizedBox(height: 20), action!],
          ]),
        ),
      );
}

/// Confirm dialog returning true when the user accepts.
Future<bool> confirm(BuildContext context,
    {required String title, required String message, String action = 'Confirm', bool destructive = false}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
      content: Text(message, style: const TextStyle(color: AppColors.textMuted, height: 1.4)),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          style: TextButton.styleFrom(foregroundColor: AppColors.textMuted),
          child: const Text('Cancel'),
        ),
        TextButton(
          onPressed: () => Navigator.pop(ctx, true),
          style: TextButton.styleFrom(foregroundColor: destructive ? AppColors.danger : AppColors.primary),
          child: Text(action),
        ),
      ],
    ),
  );
  return ok == true;
}
