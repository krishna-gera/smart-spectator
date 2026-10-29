import 'dart:convert';
import 'dart:math';

import 'package:shared_preferences/shared_preferences.dart';

/// Small app-wide preferences (first-run guide, alerts, power saver) and the
/// main phone's private key for its web-app directory entry.
class AppPrefs {
  static const _keyOnboarded = 'vyro_onboarded';
  static const _keyHealthAlerts = 'vyro_health_alerts';
  static const _keyPowerSaver = 'vyro_power_saver';
  static const _keyDirectoryOwner = 'vyro_directory_owner';

  static Future<bool> onboarded() async => (await SharedPreferences.getInstance()).getBool(_keyOnboarded) ?? false;
  static Future<void> setOnboarded() async => (await SharedPreferences.getInstance()).setBool(_keyOnboarded, true);

  static Future<bool> healthAlerts() async => (await SharedPreferences.getInstance()).getBool(_keyHealthAlerts) ?? true;
  static Future<void> setHealthAlerts(bool on) async => (await SharedPreferences.getInstance()).setBool(_keyHealthAlerts, on);

  static Future<bool> powerSaver() async => (await SharedPreferences.getInstance()).getBool(_keyPowerSaver) ?? true;
  static Future<void> setPowerSaver(bool on) async => (await SharedPreferences.getInstance()).setBool(_keyPowerSaver, on);

  /// A random secret, created once per phone, that proves to the VYRO cloud
  /// service that this phone created its directory entry; no one else can
  /// change or remove it. Never shown or sent anywhere else.
  static Future<String> directoryOwner() async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getString(_keyDirectoryOwner);
    if (existing != null && existing.length >= 32) return existing;
    final random = Random.secure();
    final owner = base64Url.encode(List<int>.generate(32, (_) => random.nextInt(256))).replaceAll('=', '');
    await prefs.setString(_keyDirectoryOwner, owner);
    return owner;
  }
}
