import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../../hub/hub_server.dart';
import 'h264_nal.dart';

/// Native decoder operations; an interface so tests can replace the platform.
abstract class VideoDecoderBackend {
  Future<int> create();
  Future<void> feed(int textureId, Uint8List data, int ptsUs);
  Future<void> release(int textureId);

  /// (textureId, width, height) whenever a decoder learns its video size.
  Stream<(int, int, int)> get videoSizes;
}

/// MediaCodec decoders rendering into Flutter textures (VideoDecoder.kt).
class PlatformVideoDecoderBackend implements VideoDecoderBackend {
  static const _channel = MethodChannel('com.smartspectator/decoder');
  static final PlatformVideoDecoderBackend instance = PlatformVideoDecoderBackend._();

  final _sizes = StreamController<(int, int, int)>.broadcast();

  PlatformVideoDecoderBackend._() {
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'onVideoSize') {
        final a = Map<String, dynamic>.from(call.arguments as Map);
        _sizes.add(((a['textureId'] as num).toInt(), (a['width'] as num).toInt(), (a['height'] as num).toInt()));
      }
    });
  }

  @override
  Stream<(int, int, int)> get videoSizes => _sizes.stream;

  @override
  Future<int> create() async => (await _channel.invokeMethod<num>('create'))!.toInt();

  @override
  Future<void> feed(int textureId, Uint8List data, int ptsUs) =>
      _channel.invokeMethod('feed', {'textureId': textureId, 'data': data, 'ptsUs': ptsUs});

  @override
  Future<void> release(int textureId) => _channel.invokeMethod('release', {'textureId': textureId});
}

enum LiveVideoState { starting, waitingForKeyframe, playing, stopped, failed }

/// Live picture for one camera on the main phone.
///
/// Subscribes to the hub's packet stream, drops packets until one the decoder
/// can start from (SPS + IDR) arrives, asks the camera for a keyframe right
/// away so the picture appears quickly, then forwards every packet.
class LiveVideoController extends ChangeNotifier {
  final String cameraId;
  final Stream<CameraPacket> packets;
  final bool Function(String cameraId) requestKeyframe;
  final VideoDecoderBackend backend;

  LiveVideoController({
    required this.cameraId,
    required this.packets,
    required this.requestKeyframe,
    VideoDecoderBackend? backend,
  }) : backend = backend ?? PlatformVideoDecoderBackend.instance;

  LiveVideoState state = LiveVideoState.starting;
  int? textureId;
  int videoWidth = 16;
  int videoHeight = 9;
  int packetsForwarded = 0;
  int packetsSkipped = 0;
  String? error;

  StreamSubscription<CameraPacket>? _packetSub;
  StreamSubscription<(int, int, int)>? _sizeSub;
  bool _disposed = false;

  double get aspectRatio => videoWidth / videoHeight;

  Future<void> start() async {
    try {
      final id = await backend.create();
      if (_disposed) {
        await backend.release(id);
        return;
      }
      textureId = id;
      _sizeSub = backend.videoSizes.listen((s) {
        final (tid, w, h) = s;
        if (tid == textureId && w > 0 && h > 0) {
          videoWidth = w;
          videoHeight = h;
          _notify();
        }
      });
      state = LiveVideoState.waitingForKeyframe;
      _packetSub = packets.where((p) => p.cameraId == cameraId).listen(_onPacket);
      requestKeyframe(cameraId);
    } catch (e) {
      state = LiveVideoState.failed;
      error = 'Video decoder unavailable: $e';
    }
    _notify();
  }

  void _onPacket(CameraPacket p) {
    final id = textureId;
    if (id == null) return;
    final payload = p.packet.payload;
    if (state == LiveVideoState.waitingForKeyframe) {
      if (!H264Nal.isDecoderEntryPoint(payload)) {
        packetsSkipped++;
        return;
      }
      state = LiveVideoState.playing;
      _notify();
    }
    packetsForwarded++;
    backend.feed(id, payload, p.packet.header.ptsUs);
  }

  /// Call when the camera's stream restarts so decoding resumes cleanly.
  void resync() {
    if (state == LiveVideoState.playing) {
      state = LiveVideoState.waitingForKeyframe;
      requestKeyframe(cameraId);
      _notify();
    }
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    state = LiveVideoState.stopped;
    _packetSub?.cancel();
    _sizeSub?.cancel();
    final id = textureId;
    if (id != null) backend.release(id);
    super.dispose();
  }
}
