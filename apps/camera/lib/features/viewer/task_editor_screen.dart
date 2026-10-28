import 'package:flutter/material.dart';

import '../../core/ai/ai_client.dart';
import '../../hub/hub_server.dart';
import '../../hub/watch_tasks.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';

/// Create an AI watch task: pick a camera, describe what to watch for in plain
/// words, optionally test how the AI understands it, then start watching.
class TaskEditorScreen extends StatefulWidget {
  final TaskWatcher watcher;
  final List<CameraLink> cameras;
  final String? initialCameraId;

  const TaskEditorScreen({super.key, required this.watcher, required this.cameras, this.initialCameraId});

  @override
  State<TaskEditorScreen> createState() => _TaskEditorScreenState();
}

class _TaskEditorScreenState extends State<TaskEditorScreen> {
  static const _examples = [
    'Tell me when the water in the washing machine reaches the MAX line',
    'Notify me when the progress bar on the laptop reaches 100% or says Done',
    'Tell me when the kettle stops steaming',
    'Tell me when the printer has finished and the paper is in the tray',
    'Tell me when someone takes the parcel from the doorstep',
  ];

  final _text = TextEditingController();
  late String? _cameraId = widget.initialCameraId ?? widget.cameras.firstOrNull?.cameraId;
  int _interval = 30;
  bool _remind = true;
  bool _keepWatching = false;
  int _autoStopMinutes = 180;

  bool _testing = false;
  bool _saving = false;
  AiReply<TaskPlan>? _preview;
  String? _previewFor;

  @override
  void initState() {
    super.initState();
    _text.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  CameraLink? get _camera => widget.cameras.where((c) => c.cameraId == _cameraId).firstOrNull;
  bool get _valid => _camera != null && _text.text.trim().length >= 8 && _text.text.trim().length <= 300;

  Future<void> _test() async {
    final cam = _camera;
    if (cam == null) return;
    setState(() {
      _testing = true;
      _preview = null;
    });
    final reply = await widget.watcher.preview(cameraId: cam.cameraId, cameraName: cam.deviceName, description: _text.text);
    if (!mounted) return;
    setState(() {
      _testing = false;
      _preview = reply;
      _previewFor = '${cam.cameraId}|${_text.text.trim()}';
    });
  }

  Future<void> _start() async {
    final cam = _camera;
    if (cam == null) return;
    setState(() => _saving = true);
    // Reuse the tested plan only if neither the camera nor the text changed.
    final plan = _previewFor == '${cam.cameraId}|${_text.text.trim()}' ? _preview?.value : null;
    await widget.watcher.create(
      cameraId: cam.cameraId,
      cameraName: cam.deviceName,
      description: _text.text,
      intervalSeconds: _interval,
      remindUntilAck: _remind,
      keepWatching: _keepWatching,
      autoStopMinutes: _autoStopMinutes,
      plan: plan,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('AI is now watching ${cam.deviceName}')));
    Navigator.of(context).pop(true);
  }

  String _intervalLabel(int s) => s < 60 ? '${s}s' : '${s ~/ 60} min';

  @override
  Widget build(BuildContext context) {
    final cam = _camera;
    final checksPerHour = 3600 ~/ _interval;
    return Scaffold(
      appBar: AppBar(title: const Text('New AI task')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 4, 18, 28),
          children: [
            const RingHeader(
              icon: Icons.auto_awesome,
              color: AppColors.ai,
              progress: 0.25,
              title: 'Watch for something',
              countRest: 'Describe it in your own words',
            ),
            const SectionHeader('Camera'),
            if (widget.cameras.isEmpty)
              const Text('Add a camera first.', style: TextStyle(color: AppColors.textMuted))
            else
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final c in widget.cameras)
                  ChoiceChip(
                    label: Text(c.deviceName),
                    selected: c.cameraId == _cameraId,
                    onSelected: (_) => setState(() => _cameraId = c.cameraId),
                    selectedColor: AppColors.primary,
                    labelStyle: TextStyle(
                        color: c.cameraId == _cameraId ? AppColors.onPrimary : AppColors.text, fontWeight: FontWeight.w600),
                    backgroundColor: AppColors.surface,
                    side: BorderSide.none,
                    showCheckmark: false,
                  ),
              ]),
            const SectionHeader('What should the AI watch for?'),
            TextField(
              controller: _text,
              minLines: 3,
              maxLines: 5,
              maxLength: 300,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(hintText: 'e.g. Tell me when the water reaches the MAX line'),
            ),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final e in _examples)
                ActionChip(
                  label: Text(e, overflow: TextOverflow.ellipsis),
                  onPressed: () => _text.text = e,
                  backgroundColor: AppColors.surface,
                  side: BorderSide.none,
                  labelStyle: const TextStyle(color: AppColors.textMuted, fontSize: 12.5),
                ),
            ]),
            const SizedBox(height: 14),
            OutlinedButton.icon(
              onPressed: _valid && !_testing ? _test : null,
              icon: _testing
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.auto_awesome, size: 18, color: AppColors.ai),
              label: Text(_testing ? 'Asking the AI…' : 'Test now with the live picture'),
            ),
            if (_preview != null) ...[const SizedBox(height: 12), _PreviewCard(reply: _preview!)],
            const SectionHeader('How it watches'),
            Card(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Check every'),
                  const SizedBox(height: 8),
                  SegmentedButton<int>(
                    segments: [for (final s in TaskWatcher.intervals) ButtonSegment(value: s, label: Text(_intervalLabel(s)))],
                    selected: {_interval},
                    onSelectionChanged: (v) => setState(() => _interval = v.first),
                    style: ButtonStyle(
                      backgroundColor: WidgetStateProperty.resolveWith(
                          (s) => s.contains(WidgetState.selected) ? AppColors.primary : AppColors.surfaceHigh),
                      foregroundColor: WidgetStateProperty.resolveWith(
                          (s) => s.contains(WidgetState.selected) ? AppColors.onPrimary : AppColors.text),
                      side: WidgetStateProperty.all(BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text('Up to $checksPerHour AI checks per hour; fewer when the picture does not change.',
                      style: const TextStyle(color: AppColors.textFaint, fontSize: 12.5)),
                  const SizedBox(height: 4),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Remind me until I mark it handled'),
                    subtitle: const Text('Repeats the alert every 2 minutes.'),
                    value: _remind,
                    onChanged: (v) => setState(() => _remind = v),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Keep watching after it happens'),
                    subtitle: const Text('Otherwise the task stops once it is done.'),
                    value: _keepWatching,
                    onChanged: (v) => setState(() => _keepWatching = v),
                  ),
                  Row(children: [
                    const Expanded(child: Text('Stop automatically after')),
                    DropdownButton<int>(
                      value: _autoStopMinutes,
                      dropdownColor: AppColors.surfaceHigh,
                      underline: const SizedBox(),
                      items: const [
                        DropdownMenuItem(value: 60, child: Text('1 hour')),
                        DropdownMenuItem(value: 180, child: Text('3 hours')),
                        DropdownMenuItem(value: 480, child: Text('8 hours')),
                      ],
                      onChanged: (v) => setState(() => _autoStopMinutes = v ?? 180),
                    ),
                  ]),
                ]),
              ),
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: _valid && !_saving ? _start : null,
              icon: const Icon(Icons.visibility_rounded),
              label: Text(cam == null ? 'Choose a camera' : 'Start watching ${cam.deviceName}'),
            ),
            const SizedBox(height: 12),
            const Text(
              'Pictures from this camera are sent to Groq (an online AI service) while the task runs. '
              'The camera shows an "AI watching" badge. AI can be wrong — don\'t rely on it for safety.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textFaint, fontSize: 12, height: 1.4),
            ),
          ],
        ),
      ),
    );
  }
}

class _PreviewCard extends StatelessWidget {
  final AiReply<TaskPlan> reply;
  const _PreviewCard({required this.reply});

  @override
  Widget build(BuildContext context) {
    final p = reply.value;
    return Card(
      color: AppColors.ai.withValues(alpha: 0.12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: p == null
            ? Text(reply.error ?? 'No answer.', style: const TextStyle(color: AppColors.danger))
            : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('The AI will check:', style: TextStyle(color: AppColors.ai, fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                Text(p.question, style: const TextStyle(fontSize: 16, height: 1.35)),
                const SizedBox(height: 10),
                Row(children: [
                  CheckCircle(checked: p.targetVisible, size: 22),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(p.targetVisible ? 'It can see what to watch' : 'It cannot see it clearly yet',
                        style: TextStyle(color: p.targetVisible ? AppColors.text : AppColors.danger)),
                  ),
                ]),
                if (p.currentState.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text('Right now: ${p.currentState}', style: const TextStyle(color: AppColors.textMuted)),
                ],
                if (p.advice.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text('Tip: ${p.advice}', style: const TextStyle(color: AppColors.warning)),
                ],
              ]),
      ),
    );
  }
}
