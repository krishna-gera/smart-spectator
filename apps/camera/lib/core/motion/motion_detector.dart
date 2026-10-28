import 'dart:typed_data';

/// Motion detection on the camera phone. Not AI: it compares the average
/// brightness of a coarse grid of blocks between frames.
///
/// - Only the luma (Y) plane is read, and only every few pixels, so it costs
///   a fraction of a millisecond per frame.
/// - Whole-picture changes (auto-exposure, lights switched on) are ignored.
/// - Motion must persist for [confirmFrames] analysed frames to start, and
///   stop for [endAfter] to end, so single-frame noise never triggers.
class MotionDetector {
  static const int gridWidth = 32;
  static const int gridHeight = 18;

  /// 0 = least sensitive, 1 = most sensitive.
  double sensitivity;

  /// Frames analysed per second; other frames are skipped.
  final double analysisFps;
  final int confirmFrames;
  final Duration endAfter;

  Float64List? _previous;
  DateTime? _lastAnalysed;
  int _consecutive = 0;
  bool _active = false;
  DateTime? _activeSince;
  DateTime? _lastMotionAt;
  double _peakScore = 0;

  MotionDetector({
    this.sensitivity = 0.5,
    this.analysisFps = 5,
    this.confirmFrames = 2,
    this.endAfter = const Duration(seconds: 3),
  });

  bool get isActive => _active;

  /// Per-block brightness change (0–255) that counts as "changed".
  double get _blockThreshold => 40 - 28 * sensitivity.clamp(0.0, 1.0); // 40 → 12

  /// Share of blocks that must change to count as motion.
  double get _minChangedFraction => 0.06 - 0.05 * sensitivity.clamp(0.0, 1.0); // 6% → 1% (medium 3.5%)

  /// Above this share of changed blocks, treat it as a lighting change.
  static const double _lightingChangeFraction = 0.85;

  void reset() {
    _previous = null;
    _lastAnalysed = null;
    _consecutive = 0;
    _active = false;
    _activeSince = null;
    _lastMotionAt = null;
    _peakScore = 0;
  }

  /// Feeds one frame's luma plane. Returns a [MotionUpdate] only when motion
  /// starts or ends; null otherwise (including skipped frames).
  MotionUpdate? process(Uint8List luma, int width, int height, int rowStride, DateTime now) {
    final last = _lastAnalysed;
    if (last != null && now.difference(last).inMicroseconds < 1e6 / analysisFps) return null;
    _lastAnalysed = now;

    final grid = blockAverages(luma, width, height, rowStride);
    final previous = _previous;
    _previous = grid;
    if (previous == null) return null;

    final score = changedFraction(previous, grid, _blockThreshold);
    final isMotion = score >= _minChangedFraction && score < _lightingChangeFraction;

    if (isMotion) {
      _consecutive++;
      _lastMotionAt = now;
      if (_active) {
        if (score > _peakScore) _peakScore = score;
      } else if (_consecutive >= confirmFrames) {
        _active = true;
        _activeSince = now;
        _peakScore = score;
        return MotionUpdate.started(now, score);
      }
    } else {
      _consecutive = 0;
      final lastMotion = _lastMotionAt;
      if (_active && lastMotion != null && now.difference(lastMotion) >= endAfter) {
        _active = false;
        final update = MotionUpdate.ended(now, _peakScore, now.difference(_activeSince!));
        _activeSince = null;
        _peakScore = 0;
        return update;
      }
    }
    return null;
  }

  /// Average brightness of each grid block, sampling every 4th pixel.
  static Float64List blockAverages(Uint8List luma, int width, int height, int rowStride) {
    final out = Float64List(gridWidth * gridHeight);
    final blockW = width / gridWidth;
    final blockH = height / gridHeight;
    const step = 4;
    for (var by = 0; by < gridHeight; by++) {
      final y0 = (by * blockH).floor();
      final y1 = ((by + 1) * blockH).floor();
      for (var bx = 0; bx < gridWidth; bx++) {
        final x0 = (bx * blockW).floor();
        final x1 = ((bx + 1) * blockW).floor();
        var sum = 0;
        var count = 0;
        for (var y = y0; y < y1; y += step) {
          final row = y * rowStride;
          for (var x = x0; x < x1; x += step) {
            final i = row + x;
            if (i < luma.length) {
              sum += luma[i];
              count++;
            }
          }
        }
        out[by * gridWidth + bx] = count == 0 ? 0 : sum / count;
      }
    }
    return out;
  }

  /// Compact 32x18 brightness fingerprint of a frame (576 bytes), sent with
  /// snapshots so the main phone can skip AI checks when nothing changed.
  static Uint8List sceneGrid(Uint8List luma, int width, int height, int rowStride) {
    final avg = blockAverages(luma, width, height, rowStride);
    return Uint8List.fromList([for (final v in avg) v.round().clamp(0, 255)]);
  }

  /// Share of the picture that changed between two fingerprints (0–1),
  /// ignoring whole-picture brightness shifts.
  static double gridChange(Uint8List a, Uint8List b, {double threshold = 12}) {
    if (a.length != b.length || a.isEmpty) return 1;
    return changedFraction(
      Float64List.fromList(a.map((v) => v.toDouble()).toList()),
      Float64List.fromList(b.map((v) => v.toDouble()).toList()),
      threshold,
    );
  }

  /// Share of blocks whose brightness moved more than [threshold], after
  /// removing the picture-wide average shift (exposure changes).
  static double changedFraction(Float64List a, Float64List b, double threshold) {
    var meanShift = 0.0;
    for (var i = 0; i < a.length; i++) {
      meanShift += b[i] - a[i];
    }
    meanShift /= a.length;
    var changed = 0;
    for (var i = 0; i < a.length; i++) {
      if ((b[i] - a[i] - meanShift).abs() > threshold) changed++;
    }
    return changed / a.length;
  }
}

enum MotionPhase { started, ended }

class MotionUpdate {
  final MotionPhase phase;
  final DateTime at;

  /// Share of the picture that changed (0–1); peak share for [MotionPhase.ended].
  final double score;
  final Duration duration;

  const MotionUpdate._(this.phase, this.at, this.score, this.duration);

  factory MotionUpdate.started(DateTime at, double score) => MotionUpdate._(MotionPhase.started, at, score, Duration.zero);

  factory MotionUpdate.ended(DateTime at, double peakScore, Duration duration) =>
      MotionUpdate._(MotionPhase.ended, at, peakScore, duration);
}
