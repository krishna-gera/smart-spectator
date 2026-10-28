import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../core/discovery/hub_discovery.dart';
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

  /// iOS can close an app's listening socket while it is in the background.
  /// Called on resume: restarts the "add by code" server if it stopped answering.
  Future<void> ensureServer() async {
    final port = _server?.port;
    if (port != null) {
      try {
        final client = HttpClient()..connectionTimeout = const Duration(seconds: 1);
        final req = await client.get('127.0.0.1', port, '/api/v1/camera/info');
        final res = await req.close().timeout(const Duration(seconds: 1));
        await res.drain<void>();
        client.close(force: true);
        if (res.statusCode == 200) return;
      } catch (_) {}
    }
    await _server?.stop();
    _server = null;
    await start();
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

  final Map<String, DateTime> _lastRelocate = {};

  /// A main phone stopped answering: look for it on the Wi-Fi (its address
  /// may have changed) and update the link. At most once every 30 s per link.
  Future<bool> relocate(HubLink link) async {
    final now = DateTime.now();
    final last = _lastRelocate[link.key];
    if (last != null && now.difference(last) < const Duration(seconds: 30)) return false;
    _lastRelocate[link.key] = now;
    final (result, found) = await HubDiscovery.relocate(link);
    if (result == LinkCheck.removed) {
      // The main phone removed this camera: forget it (shows the code again
      // if it was the last one).
      await removeHub(link.key);
      return true;
    }
    if (found == null || (found.address.host == link.hubHost && found.address.port == link.hubPort)) return false;
    await CredentialStore.moveHub(
      link.key,
      HubLink(
        hubHost: found.address.host,
        hubPort: found.address.port,
        hubName: found.name,
        cameraId: link.cameraId,
        deviceToken: link.deviceToken,
      ),
    );
    await reload();
    return true;
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
