import 'dart:async';
import 'dart:io';
import 'package:http/http.dart' as http;

import '../platform/system_bridge.dart';

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
  /// Confirms a Smart Spectator main phone (or legacy hub) answers at [ip].
  static Future<DiscoveredHub?> probeHub(String ip, {int port = 8000, String name = 'Smart Spectator main phone'}) async {
    try {
      final uri = Uri.parse('http://$ip:$port/api/v1/health');
      final res = await http.get(uri).timeout(const Duration(milliseconds: 1200));
      if (res.statusCode == 200) {
        return DiscoveredHub(ip: ip, port: port, name: name);
      }
    } catch (_) {}
    return null;
  }

  /// Finds main phones on the Wi-Fi: mDNS/NSD first (the main phone
  /// advertises itself), then a quick probe of common addresses as fallback.
  static Stream<DiscoveredHub> discoverHubs() async* {
    final seen = <String>{};

    for (final (host, port, name) in await SystemBridge.discoverHubs()) {
      final hub = await probeHub(host, port: port, name: name);
      if (hub != null && seen.add('$host:$port')) yield hub;
    }

    // Fallback for networks that block multicast.
    try {
      final interfaces = await NetworkInterface.list(includeLinkLocal: false, type: InternetAddressType.IPv4);
      for (final iface in interfaces) {
        for (final addr in iface.addresses) {
          final parts = addr.address.split('.');
          if (parts.length != 4 || addr.isLoopback) continue;
          final subnetPrefix = '${parts[0]}.${parts[1]}.${parts[2]}';
          for (final octet in const [1, 2, 10, 15, 20, 50, 100, 150]) {
            final targetIp = '$subnetPrefix.$octet';
            if (targetIp == addr.address || seen.contains('$targetIp:8000')) continue;
            final hub = await probeHub(targetIp);
            if (hub != null && seen.add('$targetIp:8000')) yield hub;
          }
        }
      }
    } catch (_) {}
  }
}
