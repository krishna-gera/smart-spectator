import 'dart:async';
import 'dart:io';
import 'package:http/http.dart' as http;

class DiscoveredHub {
  final String ip;
  final int port;
  final String name;

  DiscoveredHub({
    required this.ip,
    required this.port,
    required this.name,
  });
}

class HubDiscovery {
  /// Probes target IP or scans common local subnet gateway for active Smart Spectator Hub.
  static Future<DiscoveredHub?> probeHub(String ip, {int port = 8000}) async {
    try {
      final uri = Uri.parse('http://$ip:$port/api/v1/health');
      final res = await http.get(uri).timeout(const Duration(milliseconds: 1200));
      if (res.statusCode == 200) {
        return DiscoveredHub(
          ip: ip,
          port: port,
          name: 'Smart Spectator Hub',
        );
      }
    } catch (_) {}
    return null;
  }

  /// Scans common LAN subnet IPs (e.g. 192.168.1.x) or localhost to discover active Hubs.
  static Stream<DiscoveredHub> discoverHubs() async* {
    // 1. Probe localhost / loopback first for development
    final local = await probeHub('127.0.0.1');
    if (local != null) yield local;

    final emulatorHost = await probeHub('10.0.2.2'); // Android emulator host alias
    if (emulatorHost != null) yield emulatorHost;

    // 2. Discover local network interface IPs
    try {
      final interfaces = await NetworkInterface.list(
        includeLinkLocal: false,
        type: InternetAddressType.IPv4,
      );

      for (var iface in interfaces) {
        for (var addr in iface.addresses) {
          final parts = addr.address.split('.');
          if (parts.length == 4) {
            final subnetPrefix = '${parts[0]}.${parts[1]}.${parts[2]}';
            // Probe common host IPs (.1, .2, .10, .100, .150, .200)
            final candidateLastOctets = [1, 2, 10, 15, 20, 50, 100, 150];
            for (var octet in candidateLastOctets) {
              final targetIp = '$subnetPrefix.$octet';
              if (targetIp == addr.address) continue;
              final hub = await probeHub(targetIp);
              if (hub != null) yield hub;
            }
          }
        }
      }
    } catch (_) {}
  }
}
