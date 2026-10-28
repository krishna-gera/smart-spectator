import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:camera/camera.dart';
import '../../core/storage/credential_store.dart';
import '../../core/streaming/media_transport.dart';
import '../../core/control/control_client.dart';
import '../../core/codec/h264_encoder.dart';
import '../../core/protocol/packet_encoder.dart';
import '../../core/platform/system_bridge.dart';

class CameraScreen extends StatefulWidget {
  final DeviceCredentials credentials;
  final VoidCallback onUnpaired;

  const CameraScreen({
    super.key,
    required this.credentials,
    required this.onUnpaired,
  });

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> with WidgetsBindingObserver {
  CameraController? _cameraController;
  List<CameraDescription> _cameras = [];
  bool _isCameraInitialized = false;
  bool _isStreaming = false;

  final H264HardwareEncoder _encoder = H264HardwareEncoder();
  bool _isProcessingFrame = false;
  int _sequenceNumber = 0;
  int _framesCaptured = 0;
  int _packetsSent = 0;
  int _bytesSent = 0;
  double _fps = 0.0;
  DateTime? _lastFpsUpdate;
  int _framesInWindow = 0;

  MediaTransport? _mediaTransport;
  ControlClient? _controlClient;
  TransportStatus _transportStatus = TransportStatus.disconnected;
  StreamSubscription? _transportSub;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initCamera();
    _initNetworking();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive || state == AppLifecycleState.paused) {
      if (_isStreaming) {
        _stopStreamingPipeline();
      }
      if (_cameraController != null && _cameraController!.value.isInitialized) {
        _cameraController?.dispose();
        _cameraController = null;
        if (mounted) {
          setState(() {
            _isCameraInitialized = false;
          });
        }
      }
    } else if (state == AppLifecycleState.resumed) {
      if (!_isCameraInitialized) {
        _initCamera();
      }
    }
  }

  Future<void> _initCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras.isNotEmpty) {
        _cameraController = CameraController(
          _cameras[0],
          ResolutionPreset.high, // 720p target as per Phase 0 / SSP1
          enableAudio: false,
          imageFormatGroup: ImageFormatGroup.yuv420,
        );
        await _cameraController!.initialize();
        if (mounted) {
          setState(() {
            _isCameraInitialized = true;
          });
        }
      }
    } catch (e) {
      debugPrint('Camera initialization error: $e');
    }
  }

  void _initNetworking() {
    final creds = widget.credentials;
    if (creds.hubIp != null && creds.deviceToken != null && creds.cameraId != null) {
      _mediaTransport = MediaTransport(
        hubIp: creds.hubIp!,
        hubPort: creds.hubPort,
        cameraId: creds.cameraId!,
        deviceToken: creds.deviceToken!,
      );

      _transportSub = _mediaTransport!.statusStream.listen((status) {
        if (mounted) {
          setState(() {
            _transportStatus = status;
          });
        }
      });
    }
  }

  Future<void> _startStreamingPipeline() async {
    if (_mediaTransport == null || _cameraController == null || !_cameraController!.value.isInitialized) {
      return;
    }

    final creds = widget.credentials;
    _controlClient = ControlClient(
      hubIp: creds.hubIp!,
      hubPort: creds.hubPort,
      deviceId: creds.deviceId,
      cameraId: creds.cameraId!,
      deviceToken: creds.deviceToken!,
      sensorOrientation: _cameraController!.description.sensorOrientation,
      fpsProvider: () => _isStreaming ? _fps : null,
      onCommand: (cmd) {
        // The main phone asks for a keyframe when a viewer starts or recovers.
        if (cmd['action'] == 'request_idr') _encoder.requestKeyframe();
      },
    );

    await _mediaTransport?.connect();
    await _controlClient?.start();
    // Android stops camera access when the app leaves the foreground.
    await SystemBridge.keepScreenOn(true);

    _sequenceNumber = 0;
    _framesCaptured = 0;
    _packetsSent = 0;
    _bytesSent = 0;
    _framesInWindow = 0;
    _lastFpsUpdate = DateTime.now();

    try {
      await _cameraController!.startImageStream((CameraImage image) async {
        if (!_isStreaming || _isProcessingFrame) return;
        _isProcessingFrame = true;

        try {
          _framesCaptured++;
          _framesInWindow++;
          final now = DateTime.now();
          if (_lastFpsUpdate != null && now.difference(_lastFpsUpdate!).inMilliseconds >= 1000) {
            final elapsedSec = now.difference(_lastFpsUpdate!).inMilliseconds / 1000.0;
            if (mounted) {
              setState(() {
                _fps = _framesInWindow / elapsedSec;
              });
            }
            _framesInWindow = 0;
            _lastFpsUpdate = now;
          }

          final timestampUs = DateTime.now().microsecondsSinceEpoch;
          final packets = await _encoder.encodeImage(image, timestampUs);

          for (final pkt in packets) {
            final frameType = pkt.isKeyframe ? PacketEncoder.frameTypeIdr : PacketEncoder.frameTypeP;
            final wirePacket = PacketEncoder.encodePacket(
              frameType: frameType,
              sequenceNumber: _sequenceNumber++,
              ptsUs: pkt.ptsUs,
              payload: pkt.data,
            );

            _mediaTransport?.sendPacket(wirePacket);
            _packetsSent++;
            _bytesSent += wirePacket.length;
          }

          if (mounted && _packetsSent % 15 == 0) {
            setState(() {});
          }
        } on PlatformException catch (e) {
          debugPrint('Encoder error: $e');
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('This phone could not start its video encoder (${image.width}x${image.height}).')),
            );
          }
          unawaited(_stopStreamingPipeline());
        } catch (e) {
          debugPrint('Frame processing error: $e');
        } finally {
          _isProcessingFrame = false;
        }
      });

      if (mounted) {
        setState(() {
          _isStreaming = true;
        });
      }
    } catch (e) {
      debugPrint('Failed to start image stream: $e');
      await _encoder.stop();
      if (mounted) {
        setState(() {
          _isStreaming = false;
        });
      }
    }
  }

  Future<void> _stopStreamingPipeline() async {
    try {
      if (_cameraController != null && _cameraController!.value.isStreamingImages) {
        await _cameraController!.stopImageStream();
      }
    } catch (_) {}

    await _encoder.stop();
    _mediaTransport?.disconnect();
    _controlClient?.stop();
    _controlClient = null;
    await SystemBridge.keepScreenOn(false);

    if (mounted) {
      setState(() {
        _isStreaming = false;
        _fps = 0.0;
      });
    }
  }

  void _toggleStreaming() async {
    if (_isStreaming) {
      await _stopStreamingPipeline();
    } else {
      await _startStreamingPipeline();
    }
  }

  Future<void> _unpair() async {
    await _stopStreamingPipeline();
    await CredentialStore.clear();
    widget.onUnpaired();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _stopStreamingPipeline();
    _transportSub?.cancel();
    _mediaTransport?.dispose();
    _controlClient?.stop();
    _cameraController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final double mbSent = _bytesSent / (1024 * 1024);

    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('Smart Spectator Camera'),
        backgroundColor: const Color(0xFF1E293B),
        actions: [
          IconButton(
            icon: const Icon(Icons.link_off, color: Colors.redAccent),
            tooltip: 'Unpair Camera',
            onPressed: _unpair,
          )
        ],
      ),
      body: Column(
        children: [
          // Live Viewfinder
          Expanded(
            child: Container(
              margin: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.black,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFF334155)),
              ),
              clipBehavior: Clip.antiAlias,
              child: _isCameraInitialized
                  ? CameraPreview(_cameraController!)
                  : const Center(
                      child: CircularProgressIndicator(color: Color(0xFF38BDF8)),
                    ),
            ),
          ),

          // Stream Status Dashboard
          Container(
            padding: const EdgeInsets.all(20),
            decoration: const BoxDecoration(
              color: Color(0xFF1E293B),
              borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Main phone: ${widget.credentials.hubIp}:${widget.credentials.hubPort}',
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Container(
                              width: 8,
                              height: 8,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: _transportStatus == TransportStatus.connected
                                    ? Colors.greenAccent
                                    : (_transportStatus == TransportStatus.reconnecting
                                        ? Colors.amberAccent
                                        : Colors.redAccent),
                              ),
                            ),
                            const SizedBox(width: 6),
                            Text(
                              _transportStatus.name.toUpperCase(),
                              style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                            ),
                          ],
                        ),
                      ],
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          _isStreaming ? '${_fps.toStringAsFixed(1)} FPS' : '720p @ 30 FPS',
                          style: const TextStyle(color: Color(0xFF38BDF8), fontWeight: FontWeight.bold),
                        ),
                        if (_isStreaming) ...[
                          const SizedBox(height: 2),
                          Text(
                            '${mbSent.toStringAsFixed(2)} MB ($_framesCaptured frames, $_packetsSent pkts)',
                            style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
                          ),
                        ]
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: _toggleStreaming,
                  icon: Icon(_isStreaming ? Icons.stop : Icons.play_arrow),
                  label: Text(_isStreaming ? 'Stop Streaming' : 'Start Streaming'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _isStreaming ? Colors.redAccent : const Color(0xFF22C55E),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
