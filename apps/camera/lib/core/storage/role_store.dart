import 'package:shared_preferences/shared_preferences.dart';

/// Which job this phone does in the Smart Spectator system.
enum AppRole {
  /// Secondary phone that captures and streams video.
  camcorder,

  /// Main phone that receives streams, shows feeds and coordinates everything.
  viewer,
}

class RoleStore {
  static const _keyRole = 'ss_app_role';

  static Future<AppRole?> load() async {
    final name = (await SharedPreferences.getInstance()).getString(_keyRole);
    return AppRole.values.where((r) => r.name == name).firstOrNull;
  }

  static Future<void> save(AppRole role) async =>
      (await SharedPreferences.getInstance()).setString(_keyRole, role.name);

  static Future<void> clear() async =>
      (await SharedPreferences.getInstance()).remove(_keyRole);
}
