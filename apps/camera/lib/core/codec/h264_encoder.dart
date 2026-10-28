import 'package:camera/camera.dart';
import 'package:flutter/services.dart';

class EncodedPacket {
  final bool isKeyframe;
  final Uint8List data;
  final int ptsUs;

  EncodedPacket({
    required this.isKeyframe,
    required this.data,
    required this.ptsUs,
  });
}

/// Bridge to the Android MediaCodec H.264 encoder (VideoEncoder.kt).
///
/// The encoder is sized from the first real camera frame and re-created if the
/// camera's frame size changes, so its input always matches the frames given.
class H264HardwareEncoder {
  static const MethodChannel _channel = MethodChannel('com.smartspectator.camera/encoder');

  final int bitrate;
  final int fps;
  final int keyframeIntervalSeconds;

  int? _width;
  int? _height;
  bool _isInitialized = false;
  bool get isInitialized => _isInitialized;

  H264HardwareEncoder({
    this.bitrate = 2000000,
    this.fps = 30,
    this.keyframeIntervalSeconds = 1,
  });

  /// Planes with their real strides; the native side copies them into the
  /// codec's own layout, so padded rows and interleaved chroma are handled.
  static List<Map<String, Object>> planesOf(CameraImage image) => image.planes
      .map((p) => <String, Object>{
            'bytes': p.bytes,
            'rowStride': p.bytesPerRow,
            'pixelStride': p.bytesPerPixel ?? 1,
          })
      .toList();

  Future<bool> _ensureInitialized(int width, int height) async {
    if (_isInitialized && width == _width && height == _height) return true;
    try {
      final ok = await _channel.invokeMethod<bool>('initEncoder', {
        'width': width,
        'height': height,
        'bitrate': bitrate,
        'fps': fps,
        'keyframeInterval': keyframeIntervalSeconds,
      });
      _isInitialized = ok ?? false;
    } on PlatformException {
      _isInitialized = false;
    }
    _width = _isInitialized ? width : null;
    _height = _isInitialized ? height : null;
    return _isInitialized;
  }

  /// Encodes one camera frame. Throws [PlatformException] if the encoder
  /// cannot be created for this frame size.
  Future<List<EncodedPacket>> encodeImage(CameraImage image, int timestampUs) async {
    // Android delivers 3 planes (Y, U, V); iOS delivers NV12 (Y, interleaved CbCr).
    if (image.planes.isEmpty) return [];
    if (!await _ensureInitialized(image.width, image.height)) {
      throw PlatformException(code: 'ENCODER_INIT_FAILED', message: 'Encoder unavailable for ${image.width}x${image.height}');
    }
    try {
      final raw = await _channel.invokeMethod<List<dynamic>>('encodeFrame', {
        'planes': planesOf(image),
        'timestampUs': timestampUs,
      });
      if (raw == null) return [];
      return raw.map((item) {
        final map = Map<String, dynamic>.from(item as Map);
        return EncodedPacket(
          isKeyframe: map['isKeyframe'] as bool? ?? false,
          data: map['data'] as Uint8List? ?? Uint8List(0),
          ptsUs: (map['ptsUs'] as num?)?.toInt() ?? timestampUs,
        );
      }).toList();
    } on PlatformException {
      return [];
    }
  }

  /// JPEG of one camera frame (for event snapshots); null if it fails.
  /// [maxSize] limits the longer side (0 = full size); AI pictures are
  /// sent smaller because the AI provider limits tokens per minute.
  static Future<Uint8List?> snapshotJpeg(CameraImage image, {int quality = 70, int maxSize = 0}) async {
    try {
      return await _channel.invokeMethod<Uint8List>('snapshotJpeg', {
        'planes': planesOf(image),
        'width': image.width,
        'height': image.height,
        'quality': quality,
        'maxSize': maxSize,
      });
    } on PlatformException {
      return null;
    }
  }

  Future<void> requestKeyframe() async {
    if (!_isInitialized) return;
    try {
      await _channel.invokeMethod('requestKeyframe');
    } on PlatformException {
      // Next scheduled keyframe (≤1 s) will arrive anyway.
    }
  }

  Future<void> stop() async {
    if (!_isInitialized) return;
    try {
      await _channel.invokeMethod('stopEncoder');
    } catch (_) {}
    _isInitialized = false;
    _width = null;
    _height = null;
  }
}
