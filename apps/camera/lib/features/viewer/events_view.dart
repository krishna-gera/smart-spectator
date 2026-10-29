import 'package:flutter/material.dart';

import '../../hub/alert_service.dart';
import '../../hub/event_store.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';

String _time(DateTime t) {
  final l = t.toLocal();
  return '${l.hour.toString().padLeft(2, '0')}:${l.minute.toString().padLeft(2, '0')}';
}

String _day(DateTime t) {
  final now = DateTime.now();
  final l = t.toLocal();
  final diff = DateTime(now.year, now.month, now.day).difference(DateTime(l.year, l.month, l.day)).inDays;
  if (diff == 0) return 'Today';
  if (diff == 1) return 'Yesterday';
  return '${l.day}/${l.month}/${l.year}';
}

String _duration(CameraEvent e) {
  if (e.type == 'task_done') return 'AI task';
  if (e.type != 'motion') return 'snapshot';
  final d = e.duration;
  if (d == null) return 'ongoing';
  if (d.inSeconds < 60) return '${d.inSeconds}s';
  return '${d.inMinutes}m ${d.inSeconds % 60}s';
}

String _title(CameraEvent e) {
  if (e.type == 'task_done') return 'Task done';
  final category = e.aiCategory;
  if (category != null) return AlertService.categoryLabels[category] ?? 'Motion';
  return e.type == 'ai_check' ? 'AI check' : 'Motion';
}

Color _threatColor(String? threat) => switch (threat) {
      'high' => AppColors.danger,
      'medium' => AppColors.warning,
      _ => AppColors.ai,
    };

/// Event history on the main phone: motion events and AI checks with snapshots.
class EventsView extends StatelessWidget {
  final EventStore? store;
  final bool aiConfigured;
  final VoidCallback onChanged;

  const EventsView({super.key, required this.store, required this.aiConfigured, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final s = store;
    if (s == null) return const Center(child: CircularProgressIndicator());
    final events = s.events;
    final unseen = s.unseenCount;

    final rows = <Widget>[
      RingHeader(
        icon: Icons.notifications_rounded,
        color: AppColors.ringEvents,
        progress: events.isEmpty ? 0 : (events.length - unseen) / events.length,
        title: events.isEmpty ? 'All quiet' : 'Activity',
        countStrong: events.isEmpty ? null : '$unseen',
        countRest: events.isEmpty ? 'No events yet' : (unseen == 1 ? 'new event' : 'new events'),
      ),
    ];
    if (events.isEmpty) {
      rows.add(const Card(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Text(
            'When a camera sees motion it appears here with a snapshot and, if you turn it on, an AI description.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.textMuted, height: 1.4),
          ),
        ),
      ));
    } else {
      rows.add(Row(children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: unseen == 0
                ? null
                : () async {
                    await s.markSeen(events.map((e) => e.id));
                    onChanged();
                  },
            icon: const Icon(Icons.done_all_rounded, size: 18),
            label: const Text('Mark all seen'),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () async {
              if (await confirm(context,
                  title: 'Delete all events?',
                  message: 'All events and their snapshots will be removed from this phone.',
                  action: 'Delete',
                  destructive: true)) {
                await s.clear();
                onChanged();
              }
            },
            icon: const Icon(Icons.delete_outline_rounded, size: 18),
            label: const Text('Clear history'),
          ),
        ),
      ]));
      String? lastDay;
      for (final e in events) {
        final day = _day(e.startedAt);
        if (day != lastDay) {
          rows.add(CenteredLabel(day,
              icon: day == 'Today' ? Icons.wb_sunny_rounded : Icons.history_rounded,
              iconColor: day == 'Today' ? AppColors.primary : AppColors.textMuted));
          lastDay = day;
        }
        rows.add(Padding(padding: const EdgeInsets.only(bottom: 12), child: _EventTile(store: s, event: e, onChanged: onChanged)));
      }
    }
    return ListView(padding: const EdgeInsets.fromLTRB(18, 4, 18, 28), children: rows);
  }
}

class _Snapshot extends StatelessWidget {
  final EventStore store;
  final CameraEvent event;
  final BoxFit fit;
  const _Snapshot({required this.store, required this.event, this.fit = BoxFit.cover});

  @override
  Widget build(BuildContext context) {
    final file = store.snapshotOf(event);
    if (file == null) {
      return const ColoredBox(
        color: AppColors.surfaceHigh,
        child: Center(child: Icon(Icons.image_not_supported_outlined, color: AppColors.textFaint)),
      );
    }
    return RotatedBox(
      quarterTurns: event.rotationDegrees ~/ 90,
      child: Image.file(file, fit: fit, gaplessPlayback: true, errorBuilder: (_, _, _) => const SizedBox()),
    );
  }
}

class _EventTile extends StatelessWidget {
  final EventStore store;
  final CameraEvent event;
  final VoidCallback onChanged;
  const _EventTile({required this.store, required this.event, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final urgent = !event.seen || event.aiThreatLevel == 'high' || event.aiThreatLevel == 'medium';
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () async {
          await store.markSeen([event.id]);
          onChanged();
          if (!context.mounted) return;
          await Navigator.of(context).push(MaterialPageRoute<void>(
            builder: (_) => EventDetailScreen(store: store, event: event, onChanged: onChanged),
          ));
        },
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 14, 16, 14),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: SizedBox(width: 92, height: 68, child: _Snapshot(store: store, event: event)),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(_title(event), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 2),
                  Text('Camera: ${event.cameraName}', style: const TextStyle(color: AppColors.textMuted, fontSize: 13.5)),
                  if (event.aiSummary != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Icon(Icons.auto_awesome, size: 14, color: _threatColor(event.aiThreatLevel)),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(event.aiSummary!,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 13.5, height: 1.3, color: AppColors.textMuted)),
                        ),
                      ]),
                    )
                  else
                    Text('Duration: ${_duration(event)}', style: const TextStyle(color: AppColors.textMuted, fontSize: 13.5)),
                ]),
              ),
            ]),
          ),
          const Divider(indent: 16, endIndent: 16),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
            child: Row(children: [
              Icon(Icons.schedule_rounded, size: 18, color: urgent ? AppColors.danger : AppColors.textMuted),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${event.seen ? 'Seen' : 'New'} · at ${_time(event.startedAt)}',
                  style: TextStyle(color: urgent ? AppColors.danger : AppColors.textMuted, fontSize: 14),
                ),
              ),
              CheckCircle(checked: event.seen),
            ]),
          ),
        ]),
      ),
    );
  }
}

class EventDetailScreen extends StatelessWidget {
  final EventStore store;
  final CameraEvent event;
  final VoidCallback onChanged;
  const EventDetailScreen({super.key, required this.store, required this.event, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_title(event)),
        actions: [
          IconButton(
            tooltip: 'Delete event',
            icon: const Icon(Icons.delete_outline),
            onPressed: () async {
              await store.delete(event.id);
              onChanged();
              if (context.mounted) Navigator.of(context).pop();
            },
          ),
        ],
      ),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: ColoredBox(
            color: Colors.black,
            child: AspectRatio(
              aspectRatio: event.rotationDegrees % 180 == 0 ? 16 / 9 : 9 / 16,
              child: _Snapshot(store: store, event: event, fit: BoxFit.contain),
            ),
          ),
        ),
        const SizedBox(height: 16),
        if (event.aiSummary != null)
          Card(
            color: AppColors.ai.withValues(alpha: 0.10),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Row(children: [
                  Icon(Icons.auto_awesome, color: AppColors.ai, size: 18),
                  SizedBox(width: 8),
                  Text('AI description', style: TextStyle(fontWeight: FontWeight.w700, color: AppColors.ai)),
                ]),
                const SizedBox(height: 8),
                Text(event.aiSummary!, style: const TextStyle(fontSize: 16, height: 1.4)),
                const SizedBox(height: 10),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  if (event.aiCategory != null)
                    StatusChip(AlertService.categoryLabels[event.aiCategory] ?? event.aiCategory!, color: AppColors.ai),
                  if (event.aiThreatLevel != null) StatusChip('Threat: ${event.aiThreatLevel}', color: _threatColor(event.aiThreatLevel)),
                ]),
              ]),
            ),
          )
        else if (event.aiError != null)
          Card(
            child: ListTile(
              leading: const Icon(Icons.auto_awesome_outlined),
              title: const Text('No AI description'),
              subtitle: Text(event.aiError!, style: const TextStyle(color: AppColors.textMuted)),
            ),
          ),
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Column(children: [
              _row('Camera', event.cameraName),
              _row('When', '${_day(event.startedAt)} at ${_time(event.startedAt)}'),
              _row('Duration', _duration(event)),
              if (event.type == 'motion') _row('Picture changed', '${(event.peakScore * 100).round()}%'),
            ]),
          ),
        ),
      ]),
    );
  }

  Widget _row(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(children: [
          SizedBox(width: 130, child: Text(label, style: const TextStyle(color: AppColors.textMuted))),
          Expanded(child: Text(value)),
        ]),
      );
}

/// Bottom sheet with one camera's motion, alert and AI settings.
class CameraSettingsSheet extends StatefulWidget {
  final String cameraName;
  final CameraSettings initial;
  final bool aiConfigured;
  final Future<void> Function(CameraSettings) onChanged;

  const CameraSettingsSheet({
    super.key,
    required this.cameraName,
    required this.initial,
    required this.aiConfigured,
    required this.onChanged,
  });

  @override
  State<CameraSettingsSheet> createState() => _CameraSettingsSheetState();
}

class _CameraSettingsSheetState extends State<CameraSettingsSheet> {
  late CameraSettings _s = widget.initial;

  Future<void> _set(CameraSettings next) async {
    setState(() => _s = next);
    await widget.onChanged(next);
  }

  Future<void> _toggleAi(bool on) async {
    if (on &&
        !await confirm(context,
            title: 'Turn on AI descriptions?',
            message: 'When this camera detects motion, one snapshot is sent to Groq (an online AI service) to be described. '
                'Live video never leaves your Wi-Fi. You can turn this off at any time.',
            action: 'Turn on')) {
      return;
    }
    await _set(_s.copyWith(aiEnabled: on));
  }

  String get _sensitivityLabel => _s.sensitivity < 0.34 ? 'Low' : (_s.sensitivity < 0.67 ? 'Medium' : 'High');

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.cameraName, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Motion detection'),
            subtitle: const Text('Runs on the camera phone; video stays on your Wi-Fi.'),
            value: _s.motionEnabled,
            onChanged: (v) => _set(_s.copyWith(motionEnabled: v)),
          ),
          Row(children: [
            const Text('Sensitivity'),
            const Spacer(),
            Text(_sensitivityLabel, style: const TextStyle(color: AppColors.textMuted)),
          ]),
          Slider(
            value: _s.sensitivity,
            divisions: 10,
            onChanged: _s.motionEnabled ? (v) => setState(() => _s = _s.copyWith(sensitivity: v)) : null,
            onChangeEnd: _s.motionEnabled ? (v) => _set(_s.copyWith(sensitivity: v)) : null,
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Alerts on this phone'),
            subtitle: const Text('At most one notification per minute for this camera.'),
            value: _s.notify,
            onChanged: (v) => _set(_s.copyWith(notify: v)),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            secondary: const Icon(Icons.auto_awesome, color: AppColors.ai),
            title: const Text('AI descriptions (Groq)'),
            subtitle: Text(widget.aiConfigured
                ? 'Describe motion snapshots in alerts. You still get every motion alert.'
                : 'Not available in this build (AI service not configured).'),
            value: widget.aiConfigured && _s.aiEnabled,
            onChanged: widget.aiConfigured ? _toggleAi : null,
          ),
        ]),
      ),
    );
  }
}
