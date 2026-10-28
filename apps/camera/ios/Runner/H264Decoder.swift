import CoreMedia
import CoreVideo
import Flutter
import Foundation
import VideoToolbox

/// Hardware H.264 decoder for one camera (VideoToolbox), rendering into a
/// Flutter texture. iOS counterpart of VideoDecoder.kt.
///
/// Accepts the same Annex-B packets as Android. The session is rebuilt when
/// SPS/PPS change (e.g. the camera phone rotates) or when iOS invalidates it
/// (e.g. after the app was in the background).
final class H264Decoder: NSObject, FlutterTexture {
  private let queue: DispatchQueue
  private weak var registry: FlutterTextureRegistry?
  private let onVideoSize: (Int64, Int, Int) -> Void

  var textureId: Int64 = 0
  private(set) var framesRendered: Int64 = 0
  private(set) var packetsDropped: Int64 = 0

  private var session: VTDecompressionSession?
  private var format: CMVideoFormatDescription?
  private var sps: Data?
  private var pps: Data?
  private var reportedSize: (Int, Int) = (0, 0)

  private var latestFrame: CVPixelBuffer?
  private let frameLock = NSLock()

  init(registry: FlutterTextureRegistry, onVideoSize: @escaping (Int64, Int, Int) -> Void) {
    self.registry = registry
    self.onVideoSize = onVideoSize
    self.queue = DispatchQueue(label: "ss.video.decoder", qos: .userInitiated)
    super.init()
  }

  // MARK: FlutterTexture

  func copyPixelBuffer() -> Unmanaged<CVPixelBuffer>? {
    frameLock.lock()
    defer { frameLock.unlock() }
    guard let frame = latestFrame else { return nil }
    return Unmanaged.passRetained(frame)
  }

  // MARK: Decoding

  func feed(_ data: Data, ptsUs: Int64) {
    queue.async { [weak self] in self?.decode(data, ptsUs: ptsUs) }
  }

  func release() {
    queue.async { [weak self] in
      guard let self else { return }
      self.invalidateSession()
      self.frameLock.lock()
      self.latestFrame = nil
      self.frameLock.unlock()
    }
  }

  private func decode(_ data: Data, ptsUs: Int64) {
    var slices: [Data] = []
    var newSps: Data?
    var newPps: Data?
    for nal in H264Decoder.splitAnnexB(data) {
      guard let header = nal.first else { continue }
      switch header & 0x1F {
      case 7: newSps = nal
      case 8: newPps = nal
      case 1, 5: slices.append(nal)
      default: break  // SEI, AUD, etc.
      }
    }

    if let newSps, let newPps, newSps != sps || newPps != pps {
      sps = newSps
      pps = newPps
      invalidateSession()
      format = H264Decoder.makeFormat(sps: newSps, pps: newPps)
    }
    if session == nil, let format {
      session = H264Decoder.makeSession(format: format)
      if session != nil { reportSize(format) }
    }
    guard let session, let format, !slices.isEmpty else {
      if !slices.isEmpty { packetsDropped += 1 }
      return
    }

    // Annex-B → AVCC (4-byte big-endian NAL lengths) for VideoToolbox.
    var avcc = Data()
    for nal in slices {
      var length = UInt32(nal.count).bigEndian
      withUnsafeBytes(of: &length) { avcc.append(contentsOf: $0) }
      avcc.append(nal)
    }
    guard let sample = H264Decoder.makeSample(avcc: avcc, format: format, ptsUs: ptsUs) else {
      packetsDropped += 1
      return
    }

    let status = VTDecompressionSessionDecodeFrame(
      session, sampleBuffer: sample, flags: [], infoFlagsOut: nil
    ) { [weak self] status, _, imageBuffer, _, _ in
      guard let self, status == noErr, let imageBuffer else { return }
      self.frameLock.lock()
      self.latestFrame = imageBuffer
      self.frameLock.unlock()
      self.framesRendered += 1
      let id = self.textureId
      DispatchQueue.main.async { [weak self] in self?.registry?.textureFrameAvailable(id) }
    }
    if status == kVTInvalidSessionErr {
      // iOS tears sessions down in the background; rebuild on the next packet.
      invalidateSession()
      packetsDropped += 1
    } else if status != noErr {
      packetsDropped += 1
    }
  }

  private func reportSize(_ format: CMVideoFormatDescription) {
    let dims = CMVideoFormatDescriptionGetDimensions(format)
    let size = (Int(dims.width), Int(dims.height))
    guard size != reportedSize, size.0 > 0, size.1 > 0 else { return }
    reportedSize = size
    let id = textureId
    DispatchQueue.main.async { [weak self] in self?.onVideoSize(id, size.0, size.1) }
  }

  private func invalidateSession() {
    if let session {
      VTDecompressionSessionWaitForAsynchronousFrames(session)
      VTDecompressionSessionInvalidate(session)
    }
    session = nil
  }

  // MARK: Helpers

  /// Splits an Annex-B stream into NAL units (start codes removed).
  static func splitAnnexB(_ data: Data) -> [Data] {
    let bytes = [UInt8](data)
    var starts: [Int] = []  // index of first NAL byte after each start code
    var i = 0
    while i + 3 <= bytes.count - 1 {
      if bytes[i] == 0, bytes[i + 1] == 0, bytes[i + 2] == 1 {
        starts.append(i + 3)
        i += 3
      } else {
        i += 1
      }
    }
    var nals: [Data] = []
    for (n, start) in starts.enumerated() {
      var end = n + 1 < starts.count ? starts[n + 1] - 3 : bytes.count
      // A 4-byte start code leaves one extra zero before the next 00 00 01.
      if n + 1 < starts.count, end > start, bytes[end - 1] == 0 { end -= 1 }
      if end > start { nals.append(Data(bytes[start..<end])) }
    }
    return nals
  }

  private static func makeFormat(sps: Data, pps: Data) -> CMVideoFormatDescription? {
    var format: CMVideoFormatDescription?
    let status = sps.withUnsafeBytes { spsRaw in
      pps.withUnsafeBytes { ppsRaw -> OSStatus in
        let pointers: [UnsafePointer<UInt8>] = [
          spsRaw.bindMemory(to: UInt8.self).baseAddress!,
          ppsRaw.bindMemory(to: UInt8.self).baseAddress!,
        ]
        let sizes = [sps.count, pps.count]
        return CMVideoFormatDescriptionCreateFromH264ParameterSets(
          allocator: kCFAllocatorDefault, parameterSetCount: 2, parameterSetPointers: pointers,
          parameterSetSizes: sizes, nalUnitHeaderLength: 4, formatDescriptionOut: &format)
      }
    }
    return status == noErr ? format : nil
  }

  private static func makeSession(format: CMVideoFormatDescription) -> VTDecompressionSession? {
    // Flutter's iOS texture path expects BGRA, Metal-compatible buffers.
    let attrs: [CFString: Any] = [
      kCVPixelBufferPixelFormatTypeKey: kCVPixelFormatType_32BGRA,
      kCVPixelBufferMetalCompatibilityKey: true,
      kCVPixelBufferIOSurfacePropertiesKey: [:] as [CFString: Any],
    ]
    var session: VTDecompressionSession?
    let status = VTDecompressionSessionCreate(
      allocator: kCFAllocatorDefault, formatDescription: format, decoderSpecification: nil,
      imageBufferAttributes: attrs as CFDictionary, outputCallback: nil,
      decompressionSessionOut: &session)
    return status == noErr ? session : nil
  }

  private static func makeSample(avcc: Data, format: CMVideoFormatDescription, ptsUs: Int64) -> CMSampleBuffer? {
    var block: CMBlockBuffer?
    guard
      CMBlockBufferCreateWithMemoryBlock(
        allocator: kCFAllocatorDefault, memoryBlock: nil, blockLength: avcc.count,
        blockAllocator: kCFAllocatorDefault, customBlockSource: nil, offsetToData: 0,
        dataLength: avcc.count, flags: 0, blockBufferOut: &block) == kCMBlockBufferNoErr,
      let block
    else { return nil }
    let copied = avcc.withUnsafeBytes { raw in
      CMBlockBufferReplaceDataBytes(
        with: raw.baseAddress!, blockBuffer: block, offsetIntoDestination: 0, dataLength: avcc.count)
    }
    guard copied == kCMBlockBufferNoErr else { return nil }

    var timing = CMSampleTimingInfo(
      duration: .invalid, presentationTimeStamp: CMTime(value: ptsUs, timescale: 1_000_000),
      decodeTimeStamp: .invalid)
    var size = avcc.count
    var sample: CMSampleBuffer?
    let status = CMSampleBufferCreateReady(
      allocator: kCFAllocatorDefault, dataBuffer: block, formatDescription: format, sampleCount: 1,
      sampleTimingEntryCount: 1, sampleTimingArray: &timing, sampleSizeEntryCount: 1,
      sampleSizeArray: &size, sampleBufferOut: &sample)
    return status == noErr ? sample : nil
  }
}
