import 'dart:convert';
import 'dart:math';

import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// One main phone this camera streams to, with the credential it issued.
class HubLink {
  final String hubHost;
  final int hubPort;
  final String hubName;
  final String cameraId;
  final String deviceToken;

  const HubLink({
    required this.hubHost,
    required this.hubPort,
    required this.hubName,
    required this.cameraId,
    required this.deviceToken,
  });

  String get key => '$hubHost:$hubPort';

  Map<String, dynamic> toJson() => {
        'hub_host': hubHost,
        'hub_port': hubPort,
        'hub_name': hubName,
        'camera_id': cameraId,
        'device_token': deviceToken,
      };

  factory HubLink.fromJson(Map<String, dynamic> j) => HubLink(
        hubHost: j['hub_host'] as String,
        hubPort: (j['hub_port'] as num?)?.toInt() ?? 8000,
        hubName: j['hub_name'] as String? ?? 'Main phone',
        cameraId: j['camera_id'] as String,
        deviceToken: j['device_token'] as String,
      );
}

class DeviceCredentials {
  final String deviceId;

  /// Permanent code other phones enter to add this camera.
  final String cameraCode;

  /// Main phones this camera streams to (one or more).
  final List<HubLink> hubs;

  const DeviceCredentials({required this.deviceId, required this.cameraCode, this.hubs = const []});

  bool get isPaired => hubs.isNotEmpty;

  // Single-hub accessors kept for older call sites.
  String? get deviceToken => hubs.isEmpty ? null : hubs.first.deviceToken;
  String? get cameraId => hubs.isEmpty ? null : hubs.first.cameraId;
  String? get hubIp => hubs.isEmpty ? null : hubs.first.hubHost;
  int get hubPort => hubs.isEmpty ? 8000 : hubs.first.hubPort;
}

class CredentialStore {
  static const _keyDeviceId = 'ss_device_id';
  static const _keyCameraCode = 'ss_camera_code';
  static const _keyHubs = 'ss_hub_links';
  // Pre-multi-hub keys (migrated on first load).
  static const _keyDeviceToken = 'ss_device_token';
  static const _keyCameraId = 'ss_camera_id';
  static const _keyHubIp = 'ss_last_hub_ip';
  static const _keyHubPort = 'ss_last_hub_port';

  static Future<DeviceCredentials> load() async {
    final prefs = await SharedPreferences.getInstance();
    var deviceId = prefs.getString(_keyDeviceId);
    if (deviceId == null) {
      deviceId = 'dev_${const Uuid().v4().replaceAll('-', '').substring(0, 12)}';
      await prefs.setString(_keyDeviceId, deviceId);
    }
    var code = prefs.getString(_keyCameraCode);
    if (code == null || !RegExp(r'^\d{6}$').hasMatch(code)) {
      code = (100000 + Random.secure().nextInt(900000)).toString();
      await prefs.setString(_keyCameraCode, code);
    }

    final hubs = <HubLink>[];
    final raw = prefs.getString(_keyHubs);
    if (raw != null) {
      try {
        hubs.addAll((jsonDecode(raw) as List).map((e) => HubLink.fromJson(Map<String, dynamic>.from(e as Map))));
      } catch (_) {}
    } else {
      // Migrate a pairing made before multi-hub support.
      final token = prefs.getString(_keyDeviceToken);
      final cameraId = prefs.getString(_keyCameraId);
      final host = prefs.getString(_keyHubIp);
      if (token != null && cameraId != null && host != null) {
        hubs.add(HubLink(
          hubHost: host,
          hubPort: prefs.getInt(_keyHubPort) ?? 8000,
          hubName: 'Main phone',
          cameraId: cameraId,
          deviceToken: token,
        ));
        await _saveHubs(prefs, hubs);
      }
    }
    return DeviceCredentials(deviceId: deviceId, cameraCode: code, hubs: hubs);
  }

  /// Adds a main phone, replacing an older link to the same address.
  static Future<void> addHub(HubLink link) async {
    final prefs = await SharedPreferences.getInstance();
    final hubs = (await load()).hubs.where((h) => h.key != link.key).toList()..add(link);
    await _saveHubs(prefs, hubs);
  }

  static Future<void> removeHub(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final hubs = (await load()).hubs.where((h) => h.key != key).toList();
    await _saveHubs(prefs, hubs);
  }

  static Future<String> changeCameraCode() async {
    final code = (100000 + Random.secure().nextInt(900000)).toString();
    await (await SharedPreferences.getInstance()).setString(_keyCameraCode, code);
    return code;
  }

  /// Older single-hub API: replaces all links with one.
  static Future<void> save({
    required String deviceToken,
    required String cameraId,
    required String hubIp,
    int hubPort = 8000,
    String hubName = 'Main phone',
  }) =>
      addHub(HubLink(hubHost: hubIp, hubPort: hubPort, hubName: hubName, cameraId: cameraId, deviceToken: deviceToken));

  /// Forgets every main phone (unpair).
  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await _saveHubs(prefs, const []);
    for (final k in [_keyDeviceToken, _keyCameraId, _keyHubIp, _keyHubPort]) {
      await prefs.remove(k);
    }
  }

  static Future<void> _saveHubs(SharedPreferences prefs, List<HubLink> hubs) =>
      prefs.setString(_keyHubs, jsonEncode(hubs.map((h) => h.toJson()).toList()));
}
