import CoreImage
import Flutter
import UIKit
import UserNotifications

/// iOS implementation of the app's native channels; mirrors MainActivity.kt:
///   com.smartspectator.camera/encoder  — Camcorder Mode H.264 encoder
///   com.smartspectator/decoder         — View Mode decoders → Flutter textures
///   com.smartspectator/system          — screen wake + Bonjour discovery
///
/// iOS has no equivalent of Android's foreground service: the hub keeps
/// running only while the app is in the foreground, so "startHubService"
/// keeps the screen awake instead.
final class SmartSpectatorNativePlugin: NSObject, FlutterPlugin, UNUserNotificationCenterDelegate {
  private let textures: FlutterTextureRegistry
  private let decoderChannel: FlutterMethodChannel
  private let encoder = H264Encoder()
  private var decoders: [Int64: H264Decoder] = [:]
  private let discovery = LocalDiscovery()
  private var hubKeepsAwake = false
  private var streamKeepsAwake = false
  private lazy var ciContext = CIContext()

  static func register(with registrar: FlutterPluginRegistrar) {
    let messenger = registrar.messenger()
    let decoderChannel = FlutterMethodChannel(name: "com.smartspectator/decoder", binaryMessenger: messenger)
    let instance = SmartSpectatorNativePlugin(textures: registrar.textures(), decoderChannel: decoderChannel)
    registrar.addMethodCallDelegate(
      instance, channel: FlutterMethodChannel(name: "com.smartspectator.camera/encoder", binaryMessenger: messenger))
    registrar.addMethodCallDelegate(instance, channel: decoderChannel)
    registrar.addMethodCallDelegate(
      instance, channel: FlutterMethodChannel(name: "com.smartspectator/system", binaryMessenger: messenger))
  }

  init(textures: FlutterTextureRegistry, decoderChannel: FlutterMethodChannel) {
    self.textures = textures
    self.decoderChannel = decoderChannel
    super.init()
    // Show event alerts as banners even while the app is open.
    UNUserNotificationCenter.current().delegate = self
  }

  func userNotificationCenter(
    _ center: UNUserNotificationCenter, willPresent notification: UNNotification,
    withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
  ) {
    completionHandler([.banner, .list, .sound])
  }

  func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    let args = call.arguments as? [String: Any] ?? [:]
    switch call.method {
    // ---- Encoder
    case "initEncoder":
      let width = args["width"] as? Int ?? 1280
      let height = args["height"] as? Int ?? 720
      let bitrate = args["bitrate"] as? Int ?? 2_000_000
      let fps = args["fps"] as? Int ?? 30
      let gop = args["keyframeInterval"] as? Int ?? 1
      encoder.queue.async {
        let ok = self.encoder.configure(width: width, height: height, bitrate: bitrate, fps: fps, gopSeconds: gop)
        DispatchQueue.main.async {
          ok
            ? result(true)
            : result(FlutterError(code: "ENCODER_INIT_FAILED", message: "Failed to initialize H.264 encoder for \(width)x\(height)", details: nil))
        }
      }
    case "encodeFrame":
      guard let raw = args["planes"] as? [[String: Any]], !raw.isEmpty else {
        result(FlutterError(code: "INVALID_ARGS", message: "Expected YUV planes", details: nil))
        return
      }
      let planes = raw.compactMap { p -> PlaneData? in
        guard let bytes = p["bytes"] as? FlutterStandardTypedData else { return nil }
        return PlaneData(bytes: bytes.data, rowStride: p["rowStride"] as? Int ?? 0, pixelStride: p["pixelStride"] as? Int ?? 1)
      }
      let timestampUs = (args["timestampUs"] as? NSNumber)?.int64Value ?? Int64(Date().timeIntervalSince1970 * 1_000_000)
      encoder.queue.async {
        let packets = self.encoder.encode(planes: planes, timestampUs: timestampUs)
        DispatchQueue.main.async { result(packets) }
      }
    case "snapshotJpeg":
      let raw = args["planes"] as? [[String: Any]] ?? []
      let planes = raw.compactMap { p -> PlaneData? in
        guard let bytes = p["bytes"] as? FlutterStandardTypedData else { return nil }
        return PlaneData(bytes: bytes.data, rowStride: p["rowStride"] as? Int ?? 0, pixelStride: p["pixelStride"] as? Int ?? 1)
      }
      let width = args["width"] as? Int ?? 0
      let height = args["height"] as? Int ?? 0
      let quality = Double(args["quality"] as? Int ?? 70) / 100
      encoder.queue.async {
        var jpeg: FlutterStandardTypedData?
        if width > 0, height > 0, let pb = H264Encoder.makeNV12(planes: planes, width: width, height: height),
          let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
          let data = self.ciContext.jpegRepresentation(
            of: CIImage(cvPixelBuffer: pb), colorSpace: colorSpace,
            options: [CIImageRepresentationOption(rawValue: kCGImageDestinationLossyCompressionQuality as String): quality])
        {
          jpeg = FlutterStandardTypedData(bytes: data)
        }
        DispatchQueue.main.async { result(jpeg) }
      }
    case "requestKeyframe":
      encoder.queue.async { self.encoder.requestKeyframe() }
      result(true)
    case "stopEncoder":
      encoder.queue.async {
        self.encoder.stop()
        DispatchQueue.main.async { result(true) }
      }

    // ---- Decoders
    case "create":
      let decoder = H264Decoder(registry: textures) { [weak self] id, w, h in
        self?.decoderChannel.invokeMethod("onVideoSize", arguments: ["textureId": id, "width": w, "height": h])
      }
      let id = textures.register(decoder)
      decoder.textureId = id
      decoders[id] = decoder
      result(id)
    case "feed":
      if let id = (args["textureId"] as? NSNumber)?.int64Value,
        let data = args["data"] as? FlutterStandardTypedData,
        let decoder = decoders[id]
      {
        decoder.feed(data.data, ptsUs: (args["ptsUs"] as? NSNumber)?.int64Value ?? 0)
      }
      result(nil)
    case "stats":
      if let id = (args["textureId"] as? NSNumber)?.int64Value, let d = decoders[id] {
        result(["framesRendered": d.framesRendered, "packetsDropped": d.packetsDropped])
      } else {
        result(nil)
      }
    case "release":
      if let id = (args["textureId"] as? NSNumber)?.int64Value, let d = decoders.removeValue(forKey: id) {
        d.release()
        textures.unregisterTexture(id)
      }
      result(nil)

    // ---- System
    case "startHubService":
      hubKeepsAwake = true
      updateIdleTimer()
      result(true)
    case "stopHubService":
      hubKeepsAwake = false
      updateIdleTimer()
      result(true)
    case "keepScreenOn":
      streamKeepsAwake = args["enabled"] as? Bool ?? false
      updateIdleTimer()
      result(true)
    case "nsdRegister":
      discovery.publish(
        port: args["port"] as? Int ?? 8000, name: args["name"] as? String ?? "SmartSpectator",
        type: args["type"] as? String ?? LocalDiscovery.serviceType)
      result(true)
    case "requestNotificationPermission":
      UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
      result(true)
    case "notify":
      let content = UNMutableNotificationContent()
      content.title = args["title"] as? String ?? "Smart Spectator"
      content.body = args["body"] as? String ?? ""
      content.sound = .default
      let id = "ss_event_\(args["id"] as? Int ?? 0)"
      UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: content, trigger: nil))
      result(true)
    case "nsdUnregister":
      discovery.unpublish()
      result(true)
    case "nsdDiscover":
      let timeoutMs = (args["timeoutMs"] as? NSNumber)?.doubleValue ?? 3000
      discovery.discover(timeout: timeoutMs / 1000, type: args["type"] as? String ?? LocalDiscovery.serviceType) { hubs in
        result(hubs)
      }

    default:
      result(FlutterMethodNotImplemented)
    }
  }

  private func updateIdleTimer() {
    UIApplication.shared.isIdleTimerDisabled = hubKeepsAwake || streamKeepsAwake
  }
}
