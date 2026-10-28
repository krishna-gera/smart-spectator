import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/pairing/code_guard.dart';

/// A camera phone that has completed pairing with this main phone.
class PairedDevice {
  final String deviceId;
  final String deviceName;
  final String cameraId;
  final String tokenHash;
  final DateTime pairedAt;
  final bool revoked;

  const PairedDevice({
    required this.deviceId,
    required this.deviceName,
    required this.cameraId,
    required this.tokenHash,
    required this.pairedAt,
    this.revoked = false,
  });

  PairedDevice copyWith({bool? revoked, String? deviceName}) => PairedDevice(
        deviceId: deviceId,
        deviceName: deviceName ?? this.deviceName,
        cameraId: cameraId,
        tokenHash: tokenHash,
        pairedAt: pairedAt,
        revoked: revoked ?? this.revoked,
      );

  Map<String, dynamic> toJson() => {
        'device_id': deviceId,
        'device_name': deviceName,
        'camera_id': cameraId,
        'token_hash': tokenHash,
        'paired_at': pairedAt.toIso8601String(),
        'revoked': revoked,
      };

  factory PairedDevice.fromJson(Map<String, dynamic> j) => PairedDevice(
        deviceId: j['device_id'] as String,
        deviceName: j['device_name'] as String,
        cameraId: j['camera_id'] as String,
        tokenHash: j['token_hash'] as String,
        pairedAt: DateTime.parse(j['paired_at'] as String),
        revoked: j['revoked'] as bool? ?? false,
      );
}

/// A pairing request waiting for the user to type the PIN on the camera phone.
class PendingPairing {
  final String deviceId;
  final String deviceName;
  final String pin;
  final DateTime expiresAt;
  int attemptsRemaining;

  PendingPairing({
    required this.deviceId,
    required this.deviceName,
    required this.pin,
    required this.expiresAt,
    this.attemptsRemaining = 3,
  });
}

/// Persistence for paired devices and the per-install token secret.
abstract class DeviceStore {
  Future<String?> loadSecret();
  Future<void> saveSecret(String secret);
  Future<List<PairedDevice>> loadDevices();
  Future<void> saveDevices(List<PairedDevice> devices);
  Future<String?> loadHubCode();
  Future<void> saveHubCode(String code);
}

class InMemoryDeviceStore implements DeviceStore {
  String? _secret;
  String? _hubCode;
  List<PairedDevice> _devices = [];

  @override
  Future<String?> loadHubCode() async => _hubCode;
  @override
  Future<void> saveHubCode(String code) async => _hubCode = code;

  @override
  Future<String?> loadSecret() async => _secret;
  @override
  Future<void> saveSecret(String secret) async => _secret = secret;
  @override
  Future<List<PairedDevice>> loadDevices() async => List.of(_devices);
  @override
  Future<void> saveDevices(List<PairedDevice> devices) async => _devices = List.of(devices);
}

class SharedPrefsDeviceStore implements DeviceStore {
  static const _keySecret = 'ss_hub_token_secret';
  static const _keyDevices = 'ss_hub_paired_devices';
  static const _keyHubCode = 'ss_hub_pairing_code';

  @override
  Future<String?> loadHubCode() async => (await SharedPreferences.getInstance()).getString(_keyHubCode);

  @override
  Future<void> saveHubCode(String code) async =>
      (await SharedPreferences.getInstance()).setString(_keyHubCode, code);

  @override
  Future<String?> loadSecret() async =>
      (await SharedPreferences.getInstance()).getString(_keySecret);

  @override
  Future<void> saveSecret(String secret) async =>
      (await SharedPreferences.getInstance()).setString(_keySecret, secret);

  @override
  Future<List<PairedDevice>> loadDevices() async {
    final raw = (await SharedPreferences.getInstance()).getString(_keyDevices);
    if (raw == null) return [];
    final list = jsonDecode(raw) as List<dynamic>;
    return list.map((e) => PairedDevice.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  @override
  Future<void> saveDevices(List<PairedDevice> devices) async =>
      (await SharedPreferences.getInstance())
          .setString(_keyDevices, jsonEncode(devices.map((d) => d.toJson()).toList()));
}

sealed class VerifyResult {}

class VerifySuccess extends VerifyResult {
  final PairedDevice device;
  final String rawToken;
  VerifySuccess(this.device, this.rawToken);
}

class VerifyFailure extends VerifyResult {
  final String message;
  VerifyFailure(this.message);
}

/// Pairing, token issuing and token checks for the main phone.
///
/// Fixes two defects of the retired PC hub:
///  * a repeated pairing request keeps the existing unexpired PIN instead of
///    replacing it, so the PIN the user reads stays valid;
///  * token validity depends only on revocation, never on connection state,
///    so a camera can reconnect after any disconnect.
class DeviceRegistry {
  static const tokenPrefix = 'ss_tok_v1_';
  static final _deviceIdPattern = RegExp(r'^[a-zA-Z0-9_\-]{3,128}$');

  final DeviceStore store;
  final Duration pinTtl;
  final int maxPendingRequests;
  final DateTime Function() _now;
  final Random _random;

  final Map<String, PendingPairing> _pending = {};
  final Map<String, PairedDevice> _devices = {};
  late List<int> _secret;

  /// Permanent code shown on the main phone; any camera that enters it pairs.
  final int maxHubCodeFailures;
  final Duration hubCodeLockout;
  late CodeGuard _hubCode;

  DeviceRegistry({
    required this.store,
    this.pinTtl = const Duration(minutes: 5),
    this.maxPendingRequests = 16,
    this.maxHubCodeFailures = 10,
    this.hubCodeLockout = const Duration(minutes: 5),
    DateTime Function()? now,
    Random? random,
  })  : _now = now ?? DateTime.now,
        _random = random ?? Random.secure();

  static bool isValidDeviceId(String id) => _deviceIdPattern.hasMatch(id);

  Future<void> load() async {
    var secret = await store.loadSecret();
    if (secret == null) {
      secret = _randomHex(32);
      await store.saveSecret(secret);
    }
    _secret = utf8.encode(secret);
    _hubCode = CodeGuard(
      code: await store.loadHubCode(),
      maxFailures: maxHubCodeFailures,
      lockout: hubCodeLockout,
      now: _now,
      random: _random,
    );
    await store.saveHubCode(_hubCode.code);
    for (final d in await store.loadDevices()) {
      _devices[d.deviceId] = d;
    }
  }

  List<PendingPairing> get pendingPairings {
    _dropExpired();
    return _pending.values.toList();
  }

  List<PairedDevice> get devices => _devices.values.toList();

  /// The main phone's permanent 6-digit pairing code.
  String get hubCode => _hubCode.code;

  /// Remaining pause after too many wrong codes, or null.
  Duration? get hubCodeLockedFor => _hubCode.lockedFor;

  /// Checks the code without pairing anything (web dashboard login). Shares
  /// the same lockout as camera pairing.
  CodeCheck checkHubCode(String code) => _hubCode.check(code);

  /// Replaces the code ("Change code"); cameras already paired stay paired.
  Future<String> changeHubCode() async {
    final code = _hubCode.regenerate();
    await store.saveHubCode(code);
    return code;
  }

  /// One-step pairing: a camera sends the code shown on the main phone.
  Future<VerifyResult> pairWithHubCode(String deviceId, String deviceName, String submittedCode) async {
    final check = _hubCode.check(submittedCode);
    if (!check.ok) return VerifyFailure(check.message!);
    _pending.remove(deviceId);
    final (device, rawToken) = await _issueToken(deviceId, deviceName);
    return VerifySuccess(device, rawToken);
  }

  /// Creates a PIN, or returns the existing one while it is still valid.
  /// Returns null when too many unrelated requests are already pending.
  PendingPairing? requestPairing(String deviceId, String deviceName) {
    _dropExpired();
    final existing = _pending[deviceId];
    if (existing != null) return existing;
    if (_pending.length >= maxPendingRequests) return null;

    final pin = (100000 + _random.nextInt(900000)).toString();
    final req = PendingPairing(
      deviceId: deviceId,
      deviceName: deviceName,
      pin: pin,
      expiresAt: _now().add(pinTtl),
    );
    _pending[deviceId] = req;
    return req;
  }

  Future<VerifyResult> verifyPairing(String deviceId, String submittedPin) async {
    _dropExpired();
    final req = _pending[deviceId];
    if (req == null) {
      return VerifyFailure('No pending pairing request for this device. Request a new code.');
    }
    if (!_constantTimeEquals(req.pin, submittedPin.trim())) {
      req.attemptsRemaining--;
      if (req.attemptsRemaining <= 0) {
        _pending.remove(deviceId);
        return VerifyFailure('Too many failed attempts. Request a new code.');
      }
      return VerifyFailure('Invalid code. ${req.attemptsRemaining} attempt(s) remaining.');
    }

    _pending.remove(deviceId);
    final (device, rawToken) = await _issueToken(deviceId, req.deviceName);
    return VerifySuccess(device, rawToken);
  }

  /// Creates (or replaces) credentials for a camera that this main phone is
  /// adding by the camera's own code. The raw token is handed to the camera.
  Future<(PairedDevice, String)> issueCredential(String deviceId, String deviceName) =>
      _issueToken(deviceId, deviceName);

  Future<(PairedDevice, String)> _issueToken(String deviceId, String deviceName) async {
    final rawToken = '$tokenPrefix${_randomHex(24)}';
    final previous = _devices[deviceId];
    final device = PairedDevice(
      deviceId: deviceId,
      deviceName: deviceName,
      // Re-pairing keeps the same camera identity so history stays attached.
      cameraId: previous?.cameraId ?? 'cam_${_randomHex(6)}',
      tokenHash: _hashToken(rawToken),
      pairedAt: _now(),
    );
    _devices[deviceId] = device;
    await store.saveDevices(devices);
    return (device, rawToken);
  }

  /// Returns the paired, non-revoked device that owns [rawToken], or null.
  PairedDevice? authenticate(String? rawToken) {
    if (rawToken == null || !rawToken.startsWith(tokenPrefix)) return null;
    final hash = _hashToken(rawToken);
    for (final d in _devices.values) {
      if (!d.revoked && _constantTimeEquals(d.tokenHash, hash)) return d;
    }
    return null;
  }

  Future<bool> revoke(String deviceId) async {
    final d = _devices[deviceId];
    if (d == null) return false;
    _devices[deviceId] = d.copyWith(revoked: true);
    await store.saveDevices(devices);
    return true;
  }

  Future<bool> forget(String deviceId) async {
    final removed = _devices.remove(deviceId) != null;
    if (removed) await store.saveDevices(devices);
    return removed;
  }

  void _dropExpired() {
    final now = _now();
    _pending.removeWhere((_, r) => now.isAfter(r.expiresAt));
  }

  String _hashToken(String raw) =>
      Hmac(sha256, _secret).convert(utf8.encode(raw)).toString();

  String _randomHex(int bytes) =>
      List.generate(bytes, (_) => _random.nextInt(256).toRadixString(16).padLeft(2, '0')).join();

  static bool _constantTimeEquals(String a, String b) {
    if (a.length != b.length) return false;
    var diff = 0;
    for (var i = 0; i < a.length; i++) {
      diff |= a.codeUnitAt(i) ^ b.codeUnitAt(i);
    }
    return diff == 0;
  }
}
