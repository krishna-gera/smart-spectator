/// A main phone's LAN address. Accepts "10.0.0.5" or "10.0.0.5:8000".
class HubAddress {
  static const int defaultPort = 8000;

  final String host;
  final int port;

  const HubAddress(this.host, [this.port = defaultPort]);

  /// Returns null when [input] is not a usable host[:port].
  static HubAddress? tryParse(String input) {
    final text = input.trim().replaceFirst(RegExp(r'^https?://'), '').replaceFirst(RegExp(r'/.*$'), '');
    if (text.isEmpty) return null;
    final parts = text.split(':');
    if (parts.length > 2) return null;
    final host = parts[0];
    if (!RegExp(r'^[A-Za-z0-9.\-]+$').hasMatch(host)) return null;
    final port = parts.length == 2 ? int.tryParse(parts[1]) : defaultPort;
    if (port == null || port < 1 || port > 65535) return null;
    return HubAddress(host, port);
  }

  Uri uri(String path) => Uri(scheme: 'http', host: host, port: port, path: path);

  @override
  String toString() => port == defaultPort ? host : '$host:$port';

  @override
  bool operator ==(Object other) => other is HubAddress && other.host == host && other.port == port;

  @override
  int get hashCode => Object.hash(host, port);
}
