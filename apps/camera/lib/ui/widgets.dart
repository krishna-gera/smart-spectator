import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'theme.dart';

/// Small uppercase heading above a group of content.
class SectionHeader extends StatelessWidget {
  final String text;
  final Widget? trailing;
  const SectionHeader(this.text, {super.key, this.trailing});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 20, 4, 10),
        child: Row(children: [
          Expanded(
            child: Text(text.toUpperCase(),
                style: const TextStyle(color: AppColors.textMuted, fontSize: 12, letterSpacing: 1.1, fontWeight: FontWeight.w700)),
          ),
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
          color: filled ? color : color.withValues(alpha: 0.14),
          borderRadius: BorderRadius.circular(999),
          border: filled ? null : Border.all(color: color.withValues(alpha: 0.35)),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (icon != null)
            Icon(icon, size: 13, color: filled ? Colors.black : color)
          else
            Container(width: 7, height: 7, decoration: BoxDecoration(color: filled ? Colors.black : color, shape: BoxShape.circle)),
          const SizedBox(width: 6),
          Text(label,
              style: TextStyle(
                  color: filled ? Colors.black : color, fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 0.3)),
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
        padding: EdgeInsets.all(compact ? 14 : 20),
        child: Column(children: [
          Text(caption, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
          const SizedBox(height: 8),
          InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () {
              Clipboard.setData(ClipboardData(text: code));
              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Code copied')));
            },
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              child: Text(_spaced,
                  style: TextStyle(
                      color: AppColors.code,
                      fontSize: compact ? 30 : 42,
                      letterSpacing: compact ? 4 : 6,
                      fontWeight: FontWeight.w800,
                      fontFeatures: const [FontFeature.tabularFigures()])),
            ),
          ),
          if (onChange != null) ...[
            const SizedBox(height: 4),
            TextButton.icon(
              onPressed: onChange,
              icon: const Icon(Icons.refresh, size: 16),
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
              decoration: BoxDecoration(color: AppColors.surfaceHigh, borderRadius: BorderRadius.circular(20)),
              child: Icon(icon, size: 32, color: AppColors.primary),
            ),
            const SizedBox(height: 16),
            Text(title, textAlign: TextAlign.center, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
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
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
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
