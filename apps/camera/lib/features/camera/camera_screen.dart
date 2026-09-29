import 'dart:async';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import '../../core/storage/credential_store.dart';
import '../../core/streaming/media_transport.dart';
import '../../core/control/control_client.dart';

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

class _CameraScreenState extends State<CameraScreen> {
  CameraController? _cameraController;
  List<CameraDescription> _cameras = [];
  bool _isCameraInitialized = false;
  bool _isStreaming = false;

  MediaTransport? _mediaTransport;
  ControlClient? _controlClient;
  TransportStatus _transportStatus = TransportStatus.disconnected;
  StreamSubscription? _transportSub;

  @override
  void initState() {
    super.initState();
    _initCamera();
    _initNetworking();
  }

  Future<void> _initCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras.isNotEmpty) {
        _cameraController = CameraController(
          _cameras[0],
          ResolutionPreset.high, // 720p target as per Phase 0
          enableAudio: false,
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

      _controlClient = ControlClient(
        hubIp: creds.hubIp!,
        hubPort: creds.hubPort,
        deviceId: creds.deviceId,
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

  void _toggleStreaming() async {
    if (_isStreaming) {
      _mediaTransport?.disconnect();
      _controlClient?.stop();
      setState(() {
        _isStreaming = false;
      });
    } else {
      await _mediaTransport?.connect();
      await _controlClient?.start();
      setState(() {
        _isStreaming = true;
      });
    }
  }

  Future<void> _unpair() async {
    _mediaTransport?.disconnect();
    _controlClient?.stop();
    await CredentialStore.clear();
    widget.onUnpaired();
  }

  @override
  void dispose() {
    _transportSub?.cancel();
    _mediaTransport?.dispose();
    _controlClient?.stop();
    _cameraController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
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
                          'Hub: ${widget.credentials.hubIp}:${widget.credentials.hubPort}',
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
                    const Text(
                      '720p @ 30 FPS',
                      style: TextStyle(color: Color(0xFF38BDF8), fontWeight: FontWeight.bold),
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
