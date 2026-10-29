import 'dart:io';

/// True for a Host header a VYRO phone is reached by on the home network: an
/// IP address, a Bonjour `.local` name or localhost, with an optional port.
/// Any other name means a web page is reaching the phone through someone
/// else's domain name (DNS rebinding), so the request is refused. Requests
/// without a Host header come from apps, not browsers, and are allowed.
bool isLocalHost(String? host) {
  if (host == null || host.trim().isEmpty) return true;
  var h = host.trim().toLowerCase();
  if (h.startsWith('[')) {
    final end = h.indexOf(']');
    return end > 0 && InternetAddress.tryParse(h.substring(1, end)) != null;
  }
  final colon = h.lastIndexOf(':');
  if (colon >= 0) h = h.substring(0, colon);
  if (h.endsWith('.')) h = h.substring(0, h.length - 1);
  return InternetAddress.tryParse(h) != null || h == 'localhost' || h.endsWith('.local');
}
