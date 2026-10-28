import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/core/motion/motion_detector.dart';

const w = 320, h = 180;

/// Grey frame with an optional bright square at (x, y).
Uint8List frame({int base = 100, int? squareX, int squareY = 60, int size = 48, int stride = w}) {
  final f = Uint8List(stride * h)..fillRange(0, stride * h, base);
  if (squareX != null) {
    for (var y = squareY; y < squareY + size && y < h; y++) {
      for (var x = squareX; x < squareX + size && x < w; x++) {
        f[y * stride + x] = 240;
      }
    }
  }
  return f;
}

void main() {
  late DateTime t;
  late MotionDetector d;
  // 5 analysed frames per second → step 200 ms so every frame is analysed.
  MotionUpdate? feed(Uint8List f, {int stride = w}) {
    t = t.add(const Duration(milliseconds: 200));
    return d.process(f, w, h, stride, t);
  }

  setUp(() {
    t = DateTime(2026, 10, 28, 12);
    d = MotionDetector(sensitivity: 0.5, analysisFps: 5, confirmFrames: 2, endAfter: const Duration(seconds: 1));
  });

  test('a still scene never triggers', () {
    for (var i = 0; i < 30; i++) {
      expect(feed(frame()), isNull);
    }
    expect(d.isActive, isFalse);
  });

  test('a moving object starts motion after two changed frames, then ends when still', () {
    feed(frame());
    expect(feed(frame(squareX: 20)), isNull, reason: 'one changed frame is not enough');
    final start = feed(frame(squareX: 120));
    expect(start?.phase, MotionPhase.started);
    expect(start!.score, greaterThan(0));
    expect(d.isActive, isTrue);

    MotionUpdate? end;
    for (var i = 0; i < 10 && end == null; i++) {
      end = feed(frame(squareX: 120));
    }
    expect(end?.phase, MotionPhase.ended);
    expect(end!.duration, greaterThan(Duration.zero));
    expect(d.isActive, isFalse);
  });

  test('a whole-picture brightness change (lights, exposure) is ignored', () {
    feed(frame(base: 80));
    for (var i = 0; i < 6; i++) {
      expect(feed(frame(base: 80 + 20 * (i + 1))), isNull);
    }
  });

  test('frames arriving faster than the analysis rate are skipped', () {
    feed(frame());
    t = t.add(const Duration(milliseconds: 10));
    expect(d.process(frame(squareX: 120), w, h, w, t), isNull);
    t = t.add(const Duration(milliseconds: 10));
    expect(d.process(frame(squareX: 10), w, h, w, t), isNull);
    expect(d.isActive, isFalse);
  });

  test('sensitivity decides whether a small change counts', () {
    // A small 20x20 object (about 1–3% of the picture) moving.
    for (final (sensitivity, expectMotion) in [(0.0, false), (1.0, true)]) {
      d = MotionDetector(sensitivity: sensitivity, confirmFrames: 2);
      t = DateTime(2026, 10, 28, 12);
      MotionUpdate? got;
      for (var i = 0; i < 8; i++) {
        got ??= feed(frame(squareX: 10 + i * 30, size: 20));
      }
      expect(got?.phase == MotionPhase.started, expectMotion, reason: 'sensitivity $sensitivity');
    }
  });

  test('row padding (stride > width) is handled', () {
    const stride = w + 64;
    feed(frame(stride: stride), stride: stride);
    feed(frame(squareX: 20, stride: stride), stride: stride);
    expect(feed(frame(squareX: 140, stride: stride), stride: stride)?.phase, MotionPhase.started);
  });

  test('reset forgets the previous frame', () {
    feed(frame());
    feed(frame(squareX: 20));
    d.reset();
    expect(feed(frame(squareX: 140)), isNull);
    expect(d.isActive, isFalse);
  });
}
