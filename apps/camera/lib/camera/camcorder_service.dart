import 'dart:async';

import 'package:flutter/foundation.dart';

import '../core/pairing/code_guard.dart';
import '../core/platform/system_bridge.dart';
import '../core/storage/credential_store.dart';
import 'camera_link_server.dart';

/// Camcorder Mode state shared by its screens: this camera's identity and
/// permanent code, the main phones it streams to, and the LAN server that
/// lets main phones add it by code.
class CamcorderService extends ChangeNotifier {
  DeviceCredentials? _creds;
  CodeGuard? _guard;
  CameraLinkServer? _server;
  final _linked = StreamController<HubLink>.broadcast();

  DeviceCredentials? get credentials => _creds;
  bool get isReady => _creds != null;
  String get cameraCode => _guard?.code ?? '';
  List<HubLink> get hubs => _creds?.hubs ?? const [];

  /// Fires when a main phone adds this camera by its code.
  Stream<HubLink> get linked => _linked.stream;

  String get deviceName {
    final id = _creds?.deviceId ?? '';
    final suffix = id.length >= 4 ? id.substring(id.length - 4).toUpperCase() : id;
    return 'Camera $suffix';
  }

  Future<void> start() async {
    _creds = await CredentialStore.load();
    _guard = CodeGuard(code: _creds!.cameraCode);
    final server = CameraLinkServer(
      deviceId: _creds!.deviceId,
      deviceName: deviceName,
      guard: _guard!,
      onLinked: (link) async {
        await CredentialStore.addHub(link);
        await reload();
        _linked.add(link);
      },
    );
    try {
      final port = await server.start();
      _server = server;
      await SystemBridge.advertiseCamera(port, deviceName);
    } catch (_) {
      // Adding by camera code is unavailable; entering the main phone's code still works.
    }
    notifyListeners();
  }

  Future<void> reload() async {
    _creds = await CredentialStore.load();
    notifyListeners();
  }

  Future<void> changeCameraCode() async {
    final code = await CredentialStore.changeCameraCode();
    _guard = CodeGuard(code: code);
    // Rebuild the link server with the new code.
    await _server?.stop();
    _server = null;
    await start();
  }

  Future<void> removeHub(String key) async {
    await CredentialStore.removeHub(key);
    await reload();
  }

  Future<void> removeAllHubs() async {
    await CredentialStore.clear();
    await reload();
  }

  Future<void> stop() async {
    await _server?.stop();
    _server = null;
    await SystemBridge.stopAdvertisingHub();
  }

  @override
  void dispose() {
    stop();
    _linked.close();
    super.dispose();
  }
}
