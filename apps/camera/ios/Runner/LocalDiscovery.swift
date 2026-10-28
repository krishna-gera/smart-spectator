import Foundation

/// Bonjour (mDNS/DNS-SD) for the local hub, the iOS counterpart of NsdHelper.kt.
/// The main phone publishes "_smartspectator._tcp"; camera phones browse for it.
/// Requires NSBonjourServices and NSLocalNetworkUsageDescription in Info.plist.
/// Must be used from the main thread (NetService runs on the main run loop).
final class LocalDiscovery: NSObject, NetServiceBrowserDelegate, NetServiceDelegate {
  static let serviceType = "_smartspectator._tcp."

  private var published: NetService?
  private var browser: NetServiceBrowser?
  private var resolving: [NetService] = []
  private var results: [[String: Any]] = []
  private var completion: (([[String: Any]]) -> Void)?

  func publish(port: Int, name: String) {
    unpublish()
    let service = NetService(domain: "local.", type: LocalDiscovery.serviceType, name: name, port: Int32(port))
    service.publish()
    published = service
  }

  func unpublish() {
    published?.stop()
    published = nil
  }

  /// Browses for `timeout` seconds and returns resolved hubs as {host, port, name}.
  func discover(timeout: TimeInterval, completion: @escaping ([[String: Any]]) -> Void) {
    guard self.completion == nil else {
      completion([])  // a search is already running
      return
    }
    self.completion = completion
    results = []
    let browser = NetServiceBrowser()
    browser.delegate = self
    browser.searchForServices(ofType: LocalDiscovery.serviceType, inDomain: "local.")
    self.browser = browser
    DispatchQueue.main.asyncAfter(deadline: .now() + timeout) { [weak self] in self?.finish() }
  }

  private func finish() {
    browser?.stop()
    browser = nil
    resolving.forEach { $0.stop() }
    resolving.removeAll()
    let done = completion
    completion = nil
    done?(results)
  }

  // MARK: NetServiceBrowserDelegate

  func netServiceBrowser(_ browser: NetServiceBrowser, didFind service: NetService, moreComing: Bool) {
    service.delegate = self
    resolving.append(service)
    service.resolve(withTimeout: 2)
  }

  // MARK: NetServiceDelegate

  func netServiceDidResolveAddress(_ sender: NetService) {
    for address in sender.addresses ?? [] {
      guard let host = LocalDiscovery.ipv4String(address) else { continue }
      if !results.contains(where: { $0["host"] as? String == host && $0["port"] as? Int == sender.port }) {
        results.append(["host": host, "port": sender.port, "name": sender.name])
      }
      break
    }
  }

  private static func ipv4String(_ address: Data) -> String? {
    address.withUnsafeBytes { raw -> String? in
      guard raw.count >= MemoryLayout<sockaddr_in>.size else { return nil }
      var sin = raw.load(as: sockaddr_in.self)
      guard sin.sin_family == sa_family_t(AF_INET) else { return nil }
      var buffer = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
      guard inet_ntop(AF_INET, &sin.sin_addr, &buffer, socklen_t(INET_ADDRSTRLEN)) != nil else { return nil }
      return String(cString: buffer)
    }
  }
}
