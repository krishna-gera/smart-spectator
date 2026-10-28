import 'package:flutter/material.dart';
import 'core/storage/credential_store.dart';
import 'core/storage/role_store.dart';
import 'features/pairing/pairing_screen.dart';
import 'features/camera/camera_screen.dart';
import 'features/role/role_select_screen.dart';
import 'features/viewer/viewer_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SmartSpectatorApp());
}

class SmartSpectatorApp extends StatefulWidget {
  const SmartSpectatorApp({super.key});

  @override
  State<SmartSpectatorApp> createState() => _SmartSpectatorAppState();
}

class _SmartSpectatorAppState extends State<SmartSpectatorApp> {
  AppRole? _role;
  DeviceCredentials? _credentials;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadState();
  }

  Future<void> _loadState() async {
    final role = await RoleStore.load();
    final creds = await CredentialStore.load();
    if (!mounted) return;
    setState(() {
      _role = role;
      _credentials = creds;
      _isLoading = false;
    });
  }

  Future<void> _selectRole(AppRole role) async {
    await RoleStore.save(role);
    await _loadState();
  }

  Future<void> _changeRole() async {
    await RoleStore.clear();
    await _loadState();
  }

  Widget _home() {
    if (_isLoading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator(color: Color(0xFF38BDF8))),
      );
    }
    switch (_role) {
      case null:
        return RoleSelectScreen(onSelected: _selectRole);
      case AppRole.viewer:
        return ViewerScreen(onChangeRole: _changeRole);
      case AppRole.camcorder:
        if (_credentials != null && _credentials!.isPaired) {
          return CameraScreen(credentials: _credentials!, onUnpaired: _loadState);
        }
        return PairingScreen(onPaired: _loadState, onChangeRole: _changeRole);
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Smart Spectator',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF0F172A),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF38BDF8),
          surface: Color(0xFF1E293B),
        ),
      ),
      home: _home(),
    );
  }
}
