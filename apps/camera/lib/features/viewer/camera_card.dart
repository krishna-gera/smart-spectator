import 'package:flutter/material.dart';

import '../../core/video/live_video_controller.dart';
import '../../hub/camera_health.dart';
import '../../hub/event_store.dart';
import '../../hub/hub_server.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import 'viewer_screen.dart' show LiveVideo;

/// Label, colour and icon for a camera's health.
(String, Color, IconData) describeHealth(CameraHealth h) => switch (h) {
      CameraHealth.live => ('Live', AppColors.success, Icons.sensors_rounded),
      CameraHealth.connecting => ('Connecting video…', AppColors.warning, Icons.schedule_rounded),
      CameraHealth.online => ('Online · not streaming', AppColors.textMuted, Icons.wifi_rounded),
      CameraHealth.reconnecting => ('Reconnecting…', AppColors.warning, Icons.sync_rounded),
      CameraHealth.offline => ('Offline', AppColors.danger, Icons.wifi_off_rounded),
    };

/// One camera: live video (or its last picture), health, battery, motion.
class CameraCard extends StatelessWidget {
  final CameraLink camera;
  final LiveVideoController? controller;
  final CameraSettings settings;
  final bool aiConfigured;
  final VoidCallback? onOpen;
  final VoidCallback onSettings;
  final VoidCallback onRename;
  final VoidCallback onRemove;
  final VoidCallback? onWatch;

  const CameraCard({
    super.key,
    required this.camera,
    required this.controller,
    required this.settings,
    required this.aiConfigured,
    required this.onOpen,
    required this.onSettings,
    required this.onRename,
    required this.onRemove,
    this.onWatch,
  });

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final health = camera.health(now);
    final (label, color, icon) = describeHealth(health);
    final status = switch (health) {
      CameraHealth.live => '$label · ${camera.bitrateKbps.toStringAsFixed(0)} kbps',
      CameraHealth.offline || CameraHealth.reconnecting => camera.lastSeenAt == null
          ? '$label · waiting for it to connect'
          : '$label · last seen ${describeAgo(camera.lastSeenAt, now)}',
      _ => label,
    };
    final motion = !settings.motionEnabled ? 'Motion off' : (camera.motionActive ? 'Motion now' : 'Motion on');

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onOpen,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          AspectRatio(
            aspectRatio: 16 / 10,
            child: _Media(camera: camera, controller: controller, health: health, now: now),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 4, 4),
            child: Row(children: [
              Expanded(
                child: Text(camera.deviceName,
                    overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              ),
              _Battery(level: camera.batteryLevel, charging: camera.isCharging == true),
              PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert_rounded, color: AppColors.textMuted),
                onSelected: (v) => switch (v) {
                  'settings' => onSettings(),
                  'watch' => onWatch?.call(),
                  'rename' => onRename(),
                  _ => onRemove(),
                },
                itemBuilder: (_) => [
                  if (onWatch != null) const PopupMenuItem(value: 'watch', child: Text('Watch for something…')),
                  const PopupMenuItem(value: 'settings', child: Text('Motion, alerts & AI')),
                  const PopupMenuItem(value: 'rename', child: Text('Rename')),
                  const PopupMenuItem(value: 'remove', child: Text('Remove camera')),
                ],
              ),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
            child: Row(children: [
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 250),
                child: Icon(icon, key: ValueKey(health), size: 17, color: color),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 250),
                  layoutBuilder: (current, previous) =>
                      Stack(alignment: Alignment.centerLeft, children: [...previous, ?current]),
                  child: Text(status,
                      key: ValueKey(status), overflow: TextOverflow.ellipsis, style: TextStyle(color: color, fontSize: 13.5)),
                ),
              ),
              Text('$motion${aiConfigured && settings.aiEnabled ? ' · AI' : ''}',
                  style: TextStyle(color: camera.motionActive ? AppColors.warning : AppColors.textFaint, fontSize: 12.5)),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _Media extends StatelessWidget {
  final CameraLink camera;
  final LiveVideoController? controller;
  final CameraHealth health;
  final DateTime now;
  const _Media({required this.camera, required this.controller, required this.health, required this.now});

  @override
  Widget build(BuildContext context) {
    final live = health == CameraHealth.live && controller != null;
    final picture = camera.lastPicture;
    Widget body;
    if (live) {
      body = LiveVideo(camera: camera, controller: controller!);
    } else if (picture != null) {
      body = Stack(fit: StackFit.expand, children: [
        ColorFiltered(
          colorFilter: const ColorFilter.mode(Color(0x99000000), BlendMode.darken),
          child: RotatedBox(
            quarterTurns: camera.lastPictureRotation ~/ 90,
            child: Image.memory(picture, fit: BoxFit.cover, gaplessPlayback: true),
          ),
        ),
        Center(
          child: Text('Last picture · ${describeAgo(camera.lastPictureAt, now)}',
              style: const TextStyle(color: AppColors.text, fontSize: 13, fontWeight: FontWeight.w600)),
        ),
      ]);
    } else {
      final (label, _, icon) = describeHealth(health);
      body = Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, color: AppColors.textFaint, size: 30),
          const SizedBox(height: 8),
          Text(health == CameraHealth.online ? 'Tap Start streaming on the camera phone' : label,
              style: const TextStyle(color: AppColors.textFaint, fontSize: 13)),
        ]),
      );
    }
    return ColoredBox(
      color: Colors.black,
      child: Stack(fit: StackFit.expand, children: [
        body,
        Positioned(
          left: 10,
          top: 10,
          child: Row(children: [
            if (health == CameraHealth.live) const StatusChip('LIVE', color: AppColors.danger, filled: true),
            if (health == CameraHealth.reconnecting) const StatusChip('Reconnecting', color: AppColors.warning, filled: true),
            if (health == CameraHealth.offline) const StatusChip('Offline', color: AppColors.danger),
            if (camera.motionActive) ...[
              const SizedBox(width: 6),
              const StatusChip('Motion', color: AppColors.warning, filled: true, icon: Icons.directions_run),
            ],
            if (camera.batteryLow) ...[
              const SizedBox(width: 6),
              const StatusChip('Low battery', color: AppColors.danger, filled: true, icon: Icons.battery_alert_rounded),
            ],
          ]),
        ),
      ]),
    );
  }
}

class _Battery extends StatelessWidget {
  final double? level;
  final bool charging;
  const _Battery({required this.level, required this.charging});

  @override
  Widget build(BuildContext context) {
    final l = level;
    if (l == null) {
      return const Tooltip(message: 'Battery unknown until the camera connects', child: Icon(Icons.battery_unknown_rounded, color: AppColors.textFaint, size: 20));
    }
    final icon = charging
        ? Icons.battery_charging_full_rounded
        : l > 85
            ? Icons.battery_full_rounded
            : l > 55
                ? Icons.battery_5_bar_rounded
                : l > 30
                    ? Icons.battery_3_bar_rounded
                    : l > 15
                        ? Icons.battery_2_bar_rounded
                        : Icons.battery_alert_rounded;
    final color = charging ? AppColors.success : (l <= 15 ? AppColors.danger : (l <= 30 ? AppColors.warning : AppColors.textMuted));
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, color: color, size: 19),
      const SizedBox(width: 3),
      Text('${l.round()}%', style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
    ]);
  }
}
