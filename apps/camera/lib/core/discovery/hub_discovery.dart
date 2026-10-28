import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

import '../pairing/pairing_client.dart';
import '../platform/system_bridge.dart';

class DiscoveredHub {
  final HubAddress address;
  final String name;

  DiscoveredHub({required this.address, required this.name});

  String get ip => address.host;
  int get port => address.port;
}

class HubDiscovery {
  /// Confirms a Smart Spectator main phone answers at [address].
  static Future<DiscoveredHub?> probeHub(HubAddress address, {String? name}) async {
    try {
      final res = await http.get(address.uri('/api/v1/health')).timeout(const Duration(milliseconds: 1500));
      if (res.statusCode != 200) return null;
      final body = jsonDecode(res.body);
      if (body is! Map || body['role'] != 'main_phone') return null;
      return DiscoveredHub(address: address, name: body['name'] as String? ?? name ?? 'VYRO main phone');
    } catch (_) {
      return null;
    }
  }

  /// Finds main phones on this Wi-Fi: Bonjour/NSD (the main phone announces
  /// itself) plus a quick parallel probe of common addresses for networks
  /// that block multicast. Results arrive as they are confirmed.
  static Stream<DiscoveredHub> discoverHubs({Duration timeout = const Duration(seconds: 3)}) {
    final out = StreamController<DiscoveredHub>();
    final seen = <HubAddress>{};
    final pending = <Future<void>>[];

    void check(HubAddress a, {String? name}) {
      if (!seen.add(a)) return;
      pending.add(probeHub(a, name: name).then((hub) {
        if (hub != null && !out.isClosed) out.add(hub);
      }));
    }

    Future<void> run() async {
      final nsd = SystemBridge.discoverHubs(timeout: timeout).then((found) {
        for (final (host, port, name) in found) {
          check(HubAddress(host, port), name: name);
        }
      });
      try {
        final interfaces = await NetworkInterface.list(includeLinkLocal: false, type: InternetAddressType.IPv4);
        for (final iface in interfaces) {
          for (final addr in iface.addresses) {
            final parts = addr.address.split('.');
            if (parts.length != 4 || addr.isLoopback) continue;
            for (final octet in const [1, 2, 10, 15, 20, 50, 100, 150]) {
              final ip = '${parts[0]}.${parts[1]}.${parts[2]}.$octet';
              if (ip != addr.address) check(HubAddress(ip));
            }
          }
        }
      } catch (_) {}
      await nsd;
      await Future.wait(pending);
      await out.close();
    }

    run();
    return out.stream;
  }
}
