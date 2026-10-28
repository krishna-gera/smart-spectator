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

  static Future<DiscoveredCamera?> probe(HubAddress address) async {
    try {
      final res = await http.get(address.uri('/api/v1/camera/info')).timeout(const Duration(milliseconds: 1500));
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

  /// Bonjour/NSD first, then a quick probe of common addresses.
  static Stream<DiscoveredCamera> discover({Duration timeout = const Duration(seconds: 3)}) {
    final out = StreamController<DiscoveredCamera>();
    final seen = <HubAddress>{};
    final ids = <String>{};
    final pending = <Future<void>>[];

    void check(HubAddress a) {
      if (!seen.add(a)) return;
      pending.add(probe(a).then((cam) {
        if (cam != null && ids.add(cam.deviceId) && !out.isClosed) out.add(cam);
      }));
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
            for (final octet in const [1, 2, 10, 15, 20, 50, 100, 150]) {
              final ip = '${p[0]}.${p[1]}.${p[2]}.$octet';
              if (ip != addr.address) check(HubAddress(ip, cameraPort));
            }
          }
        }
      } catch (_) {}
      await nsd;
      await Future.wait(pending);
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

  static String? _detail(String body) {
    try {
      final d = jsonDecode(body);
      return d is Map ? d['detail'] as String? : null;
    } catch (_) {
      return null;
    }
  }
}
