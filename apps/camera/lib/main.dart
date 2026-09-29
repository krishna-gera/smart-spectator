import 'package:flutter/material.dart';
import 'core/storage/credential_store.dart';
import 'features/pairing/pairing_screen.dart';
import 'features/camera/camera_screen.dart';

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
  DeviceCredentials? _credentials;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadState();
  }

  Future<void> _loadState() async {
    final creds = await CredentialStore.load();
    setState(() {
      _credentials = creds;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Smart Spectator Camera',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF0F172A),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF38BDF8),
          surface: Color(0xFF1E293B),
        ),
      ),
      home: _isLoading
          ? const Scaffold(
              body: Center(
                child: CircularProgressIndicator(color: Color(0xFF38BDF8)),
              ),
            )
          : (_credentials != null && _credentials!.isPaired)
              ? CameraScreen(
                  credentials: _credentials!,
                  onUnpaired: _loadState,
                )
              : PairingScreen(
                  onPaired: _loadState,
                ),
    );
  }
}
