import 'package:flutter/material.dart';

import 'camera/camcorder_service.dart';
import 'core/platform/system_bridge.dart';
import 'core/storage/app_prefs.dart';
import 'core/storage/role_store.dart';
import 'features/camera/camera_screen.dart';
import 'features/onboarding/onboarding_screen.dart';
import 'features/pairing/pairing_screen.dart';
import 'features/role/role_select_screen.dart';
import 'features/viewer/viewer_screen.dart';
import 'ui/theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SmartSpectatorApp());
}

class SmartSpectatorApp extends StatefulWidget {
  const SmartSpectatorApp({super.key});

  @override
  State<SmartSpectatorApp> createState() => _SmartSpectatorAppState();
}

class _SmartSpectatorAppState extends State<SmartSpectatorApp> with WidgetsBindingObserver {
  final _navigator = GlobalKey<NavigatorState>();
  AppRole? _role;
  bool _loading = true;
  bool _onboarded = true;
  CamcorderService? _camcorder;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _camcorder?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _camcorder?.ensureServer();
  }

  Future<void> _load() async {
    final role = await RoleStore.load();
    // Existing installs (a role is already chosen) skip the first-run guide.
    final onboarded = role != null || await AppPrefs.onboarded();
    if (role == AppRole.camcorder) {
      await _startCamcorder();
    } else {
      _stopCamcorder();
    }
    if (!mounted) return;
    setState(() {
      _role = role;
      _onboarded = onboarded;
      _loading = false;
    });
  }

  Future<void> _startCamcorder() async {
    if (_camcorder != null) return;
    final service = CamcorderService();
    _camcorder = service;
    // A camera phone must not auto-lock: iOS freezes locked apps, and then
    // main phones can neither find nor reach it. Power saver blacks the screen.
    await SystemBridge.keepScreenOn(true);
    service.addListener(_onCamcorderChanged);
    await service.start();
  }

  void _stopCamcorder() {
    if (_camcorder != null) SystemBridge.keepScreenOn(false);
    _camcorder
      ?..removeListener(_onCamcorderChanged)
      ..dispose();
    _camcorder = null;
  }

  void _onCamcorderChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _selectRole(AppRole role) async {
    await RoleStore.save(role);
    await _load();
  }

  Future<void> _changeRole() async {
    await RoleStore.clear();
    await _load();
  }

  void _addMainPhone() {
    final service = _camcorder;
    if (service == null) return;
    _navigator.currentState?.push(MaterialPageRoute<void>(
      builder: (ctx) => PairingScreen(
        service: service,
        addingAnother: true,
        onPaired: () => Navigator.of(ctx).pop(),
        onChangeRole: _changeRole,
      ),
    ));
  }

  Widget _home() {
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (!_onboarded) {
      return OnboardingScreen(onDone: () async {
        await AppPrefs.setOnboarded();
        setState(() => _onboarded = true);
      });
    }
    switch (_role) {
      case null:
        return RoleSelectScreen(onSelected: _selectRole);
      case AppRole.viewer:
        return ViewerScreen(onChangeRole: _changeRole);
      case AppRole.camcorder:
        final service = _camcorder!;
        if (!service.isReady) return const Scaffold(body: Center(child: CircularProgressIndicator()));
        if (service.credentials!.isPaired) {
          return CameraScreen(service: service, onAddMainPhone: _addMainPhone, onChangeRole: _changeRole);
        }
        return PairingScreen(service: service, onPaired: service.reload, onChangeRole: _changeRole);
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'VYRO',
      debugShowCheckedModeBanner: false,
      navigatorKey: _navigator,
      theme: AppTheme.dark(),
      home: _home(),
    );
  }
}
