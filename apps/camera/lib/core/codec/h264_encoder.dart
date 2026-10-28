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

class H264HardwareEncoder {
  static const MethodChannel _channel = MethodChannel('com.smartspectator.camera/encoder');

  bool _isInitialized = false;
  bool get isInitialized => _isInitialized;

  /// Concatenates CameraImage plane buffers into a contiguous YUV byte stream
  static Uint8List extractYuvFromImage(CameraImage image) {
    if (image.planes.length == 1) {
      return image.planes[0].bytes;
    }
    final int totalBytes = image.planes.fold(0, (sum, p) => sum + p.bytes.length);
    final Uint8List yuvBytes = Uint8List(totalBytes);
    int offset = 0;
    for (final plane in image.planes) {
      yuvBytes.setRange(offset, offset + plane.bytes.length, plane.bytes);
      offset += plane.bytes.length;
    }
    return yuvBytes;
  }

  Future<bool> init({
    int width = 1280,
    int height = 720,
    int bitrate = 2000000,
    int fps = 30,
    int keyframeInterval = 1,
  }) async {
    try {
      final success = await _channel.invokeMethod<bool>('initEncoder', {
        'width': width,
        'height': height,
        'bitrate': bitrate,
        'fps': fps,
        'keyframeInterval': keyframeInterval,
      });
      _isInitialized = success ?? false;
      return _isInitialized;
    } on PlatformException catch (_) {
      _isInitialized = false;
      return false;
    }
  }

  Future<List<EncodedPacket>> encodeYuvFrame(
    Uint8List yuvData,
    int width,
    int height,
    int timestampUs,
  ) async {
    if (!_isInitialized) return [];

    try {
      final rawResults = await _channel.invokeMethod<List<dynamic>>('encodeFrame', {
        'yuvData': yuvData,
        'width': width,
        'height': height,
        'timestampUs': timestampUs,
      });

      if (rawResults == null || rawResults.isEmpty) return [];

      return rawResults.map((item) {
        final map = Map<String, dynamic>.from(item as Map);
        return EncodedPacket(
          isKeyframe: map['isKeyframe'] as bool? ?? false,
          data: map['data'] as Uint8List? ?? Uint8List(0),
          ptsUs: (map['ptsUs'] as num?)?.toInt() ?? timestampUs,
        );
      }).toList();
    } on PlatformException catch (_) {
      return [];
    }
  }

  Future<void> stop() async {
    if (!_isInitialized) return;
    try {
      await _channel.invokeMethod('stopEncoder');
    } catch (_) {}
    _isInitialized = false;
  }
}
