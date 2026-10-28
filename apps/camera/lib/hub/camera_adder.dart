import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../core/pairing/pairing_client.dart';
import '../core/platform/system_bridge.dart';
import 'device_registry.dart';

/// A camera phone found on the Wi-Fi (Camcorder Mode advertises itself).
class DiscoveredCamera {
  final HubAddress address;
  final String deviceId;
  final String name;

  const DiscoveredCamera({required this.address, required this.deviceId, required this.name});
}

/// Main phone side of "add a camera by the camera's code".
class CameraAdder {
  static const int cameraPort = 8100;

  static Future<DiscoveredCamera?> probe(HubAddress address, {Duration timeout = const Duration(milliseconds: 1500)}) async {
    try {
      final res = await http.get(address.uri('/api/v1/camera/info')).timeout(timeout);
      if (res.statusCode != 200) return null;
      final body = jsonDecode(res.body);
      if (body is! Map || body['role'] != 'camera' || body['device_id'] is! String) return null;
      return DiscoveredCamera(
        address: address,
        deviceId: body['device_id'] as String,
        name: body['device_name'] as String? ?? 'Camera',
      );
    } catch (_) {
      return null;
    }
  }

  /// Bonjour/NSD plus a scan of this Wi-Fi's addresses (camera port), so a
  /// camera is found even where Bonjour is blocked.
  static Stream<DiscoveredCamera> discover({Duration timeout = const Duration(seconds: 3), bool fullScan = true}) {
    final out = StreamController<DiscoveredCamera>();
    final seen = <HubAddress>{};
    final ids = <String>{};
    final pending = <Future<void>>[];

    // Limit parallel probes so a /24 scan does not flood the phone.
    var active = 0;
    final queue = <HubAddress>[];
    void pump() {
      while (active < 48 && queue.isNotEmpty) {
        final a = queue.removeLast();
        active++;
        pending.add(probe(a, timeout: const Duration(milliseconds: 900)).then((cam) {
          active--;
          if (cam != null && ids.add(cam.deviceId) && !out.isClosed) out.add(cam);
          pump();
        }));
      }
    }

    void check(HubAddress a) {
      if (!seen.add(a)) return;
      queue.add(a);
      pump();
    }

    Future<void> run() async {
      final nsd = SystemBridge.discover(SystemBridge.cameraServiceType, timeout: timeout).then((found) {
        for (final (host, port, _) in found) {
          check(HubAddress(host, port));
        }
      });
      try {
        for (final iface in await NetworkInterface.list(includeLinkLocal: false, type: InternetAddressType.IPv4)) {
          for (final addr in iface.addresses) {
            final p = addr.address.split('.');
            if (p.length != 4 || addr.isLoopback) continue;
            for (var octet = fullScan ? 254 : 0; octet >= 1; octet--) {
              final ip = '${p[0]}.${p[1]}.${p[2]}.$octet';
              if (ip != addr.address) check(HubAddress(ip, cameraPort));
            }
          }
        }
      } catch (_) {}
      await nsd;
      // Probes started later add to [pending]; wait until all are done.
      while (true) {
        final n = pending.length;
        await Future.wait(List.of(pending));
        if (pending.length == n && queue.isEmpty) break;
      }
      await out.close();
    }

    run();
    return out.stream;
  }

  /// Adds [camera] to this main phone. Returns null on success, or a message.
  ///
  /// 1. Check the code with the camera (nothing changes if it is wrong).
  /// 2. Issue the camera's credential on this main phone.
  /// 3. Hand the credential to the camera, which then streams here.
  static Future<String?> add({
    required DiscoveredCamera camera,
    required String code,
    required DeviceRegistry registry,
    required int hubPort,
    required String hubName,
  }) async {
    try {
      final check = await http
          .post(camera.address.uri('/api/v1/camera/link/check'),
              headers: {'Content-Type': 'application/json'}, body: jsonEncode({'code': code.trim()}))
          .timeout(const Duration(seconds: 5));
      if (check.statusCode != 200) return _detail(check.body) ?? 'The camera refused the code.';

      final (device, token) = await registry.issueCredential(camera.deviceId, camera.name);
      final link = await http
          .post(camera.address.uri('/api/v1/camera/link'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode({
                'code': code.trim(),
                'hub_port': hubPort,
                'hub_name': hubName,
                'camera_id': device.cameraId,
                'device_token': token,
              }))
          .timeout(const Duration(seconds: 5));
      if (link.statusCode != 200) return _detail(link.body) ?? 'The camera could not be added.';
      return null;
    } catch (_) {
      return 'Could not reach the camera. Make sure it is open in Camcorder Mode on the same Wi-Fi.';
    }
  }

  /// One-step add: finds the camera on this Wi-Fi whose code is [code] and
  /// links it. Returns the camera's name, or throws [AddCameraError].
  static Future<String> addByCode({
    required String code,
    required DeviceRegistry registry,
    required int hubPort,
    required String hubName,
    void Function(String status)? onStatus,
    Stream<DiscoveredCamera> Function()? discovery,
  }) async {
    onStatus?.call('Looking for the camera on this Wi-Fi…');
    var found = 0;
    String? lastError;
    final tried = <String>{};
    await for (final cam in (discovery ?? discover)()) {
      if (!tried.add(cam.deviceId)) continue;
      found++;
      onStatus?.call('Checking ${cam.name}…');
      final check = await _checkCode(cam, code);
      if (check == null) {
        onStatus?.call('Connecting ${cam.name}…');
        final error = await add(camera: cam, code: code, registry: registry, hubPort: hubPort, hubName: hubName);
        if (error == null) return cam.name;
        lastError = error;
      } else {
        lastError = check;
      }
    }
    if (found == 0) {
      throw const AddCameraError(
          'No camera found. Open VYRO on the camera phone, choose Camera, and keep both phones on the same Wi-Fi.');
    }
    throw AddCameraError(found == 1 && lastError != null ? lastError : 'No camera accepted that code. Check the code on the camera phone.');
  }

  /// Null if [code] is right for [camera], else the camera's message.
  static Future<String?> _checkCode(DiscoveredCamera camera, String code) async {
    try {
      final res = await http
          .post(camera.address.uri('/api/v1/camera/link/check'),
              headers: {'Content-Type': 'application/json'}, body: jsonEncode({'code': code.trim()}))
          .timeout(const Duration(seconds: 5));
      return res.statusCode == 200 ? null : (_detail(res.body) ?? 'The camera refused the code.');
    } catch (_) {
      return 'Could not reach ${camera.name}.';
    }
  }

  static String? _detail(String body) {
    try {
      final d = jsonDecode(body);
      return d is Map ? d['detail'] as String? : null;
    } catch (_) {
      return null;
    }
  }
}

class AddCameraError implements Exception {
  final String message;
  const AddCameraError(this.message);
  @override
  String toString() => message;
}
