import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

import '../pairing/pairing_client.dart';
import '../storage/credential_store.dart';
import '../platform/system_bridge.dart';

class DiscoveredHub {
  final HubAddress address;
  final String name;

  DiscoveredHub({required this.address, required this.name});

  String get ip => address.host;
  int get port => address.port;
}

enum LinkCheck { found, removed, notFound }

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

  /// Finds the main phone that issued [link]'s token, wherever it is on the
  /// Wi-Fi now: the hub at a new address, [LinkCheck.removed] if that main
  /// phone removed this camera, or [LinkCheck.notFound].
  static Future<(LinkCheck, DiscoveredHub?)> relocate(HubLink link) async {
    Future<(LinkCheck, DiscoveredHub?)?> ask(DiscoveredHub hub) async {
      try {
        final res = await http
            .get(hub.address.uri('/api/v1/devices/me'), headers: {'Authorization': 'Bearer ${link.deviceToken}'})
            .timeout(const Duration(seconds: 3));
        if (res.statusCode == 410) return (LinkCheck.removed, hub);
        if (res.statusCode != 200) return null;
        final body = jsonDecode(res.body);
        if (body is Map && body['camera_id'] == link.cameraId) {
          return (LinkCheck.found, DiscoveredHub(address: hub.address, name: body['hub_name'] as String? ?? hub.name));
        }
      } catch (_) {}
      return null;
    }

    // Still at the saved address (just restarting)? Then nothing to do.
    final here = await ask(DiscoveredHub(address: HubAddress(link.hubHost, link.hubPort), name: link.hubName));
    if (here != null) return here;
    await for (final hub in discoverHubs()) {
      final answer = await ask(hub);
      if (answer != null) return answer;
    }
    return (LinkCheck.notFound, null);
  }

  /// Finds main phones on this Wi-Fi: Bonjour/NSD (the main phone announces
  /// itself) plus a scan of this network's addresses for networks that block
  /// multicast. Results arrive as they are confirmed.
  static Stream<DiscoveredHub> discoverHubs({Duration timeout = const Duration(seconds: 3)}) {
    final out = StreamController<DiscoveredHub>();
    final seen = <HubAddress>{};
    final pending = <Future<void>>[];
    final queue = <(HubAddress, String?)>[];
    var active = 0;

    void pump() {
      while (active < 48 && queue.isNotEmpty) {
        final (a, name) = queue.removeLast();
        active++;
        pending.add(probeHub(a, name: name).then((hub) {
          active--;
          if (hub != null && !out.isClosed) out.add(hub);
          pump();
        }));
      }
    }

    void check(HubAddress a, {String? name}) {
      if (!seen.add(a)) return;
      queue.add((a, name));
      pump();
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
            for (var octet = 254; octet >= 1; octet--) {
              final ip = '${parts[0]}.${parts[1]}.${parts[2]}.$octet';
              if (ip != addr.address) check(HubAddress(ip));
            }
          }
        }
      } catch (_) {}
      await nsd;
      while (true) {
        final n = pending.length;
        await Future.wait(List.of(pending));
        if (pending.length == n && queue.isEmpty) break;
      }
      await out.close();
    }

    run();
    return out.stream;
  }
}
