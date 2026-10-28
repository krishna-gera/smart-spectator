import 'package:shared_preferences/shared_preferences.dart';

/// Small app-wide preferences (first-run guide, alerts, power saver).
class AppPrefs {
  static const _keyOnboarded = 'vyro_onboarded';
  static const _keyHealthAlerts = 'vyro_health_alerts';
  static const _keyPowerSaver = 'vyro_power_saver';

  static Future<bool> onboarded() async => (await SharedPreferences.getInstance()).getBool(_keyOnboarded) ?? false;
  static Future<void> setOnboarded() async => (await SharedPreferences.getInstance()).setBool(_keyOnboarded, true);

  static Future<bool> healthAlerts() async => (await SharedPreferences.getInstance()).getBool(_keyHealthAlerts) ?? true;
  static Future<void> setHealthAlerts(bool on) async => (await SharedPreferences.getInstance()).setBool(_keyHealthAlerts, on);

  static Future<bool> powerSaver() async => (await SharedPreferences.getInstance()).getBool(_keyPowerSaver) ?? true;
  static Future<void> setPowerSaver(bool on) async => (await SharedPreferences.getInstance()).setBool(_keyPowerSaver, on);
}
