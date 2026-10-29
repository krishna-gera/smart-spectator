import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../camera/camera_link_server.dart';
import '../../ui/theme.dart';

/// Asks the camera's owner whether a main phone that typed this camera's code
/// may receive its video. Nothing is shared until they tap Allow; the question
/// closes by itself (as "no") when the main phone stops waiting.
Future<bool> askToAllowMainPhone(BuildContext context, LinkRequest request) async {
  HapticFeedback.heavyImpact();
  BuildContext? dialog;
  request.closed.then((_) {
    final d = dialog;
    if (d != null && d.mounted) Navigator.of(d).pop(false);
  });
  final allowed = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) {
      dialog = ctx;
      return AlertDialog(
        title: const Text('Allow this main phone?', style: TextStyle(fontWeight: FontWeight.w800)),
        content: Text(
          '“${request.hubName}”${request.hubName.contains(request.hubHost) ? '' : ' (${request.hubHost})'} entered this camera\'s code '
          'and wants to receive its live video and pictures.\n\n'
          'Only allow phones you know.',
          style: const TextStyle(color: AppColors.textMuted, height: 1.4),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            style: TextButton.styleFrom(foregroundColor: AppColors.textMuted),
            child: const Text('Don\'t allow'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: AppColors.primary),
            child: const Text('Allow'),
          ),
        ],
      );
    },
  );
  dialog = null;
  return allowed == true;
}
