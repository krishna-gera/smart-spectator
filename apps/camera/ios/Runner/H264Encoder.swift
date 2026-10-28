import CoreMedia
import Flutter
import CoreVideo
import Foundation
import VideoToolbox

/// One YUV plane as delivered by the Flutter camera plugin.
struct PlaneData {
  let bytes: Data
  let rowStride: Int
  let pixelStride: Int
}

/// Hardware H.264 encoder (VideoToolbox), the iOS counterpart of VideoEncoder.kt.
///
/// Output matches the Android encoder exactly: Annex-B byte stream, one map per
/// access unit, with SPS/PPS prepended to every keyframe so a viewer can start
/// at any keyframe. All methods must be called on `queue`.
final class H264Encoder {
  let queue = DispatchQueue(label: "ss.video.encoder", qos: .userInitiated)

  private var session: VTCompressionSession?
  private(set) var width = 0
  private(set) var height = 0
  private var forceKeyframe = false
  private var pending: [[String: Any]] = []
  private let pendingLock = NSLock()

  func configure(width: Int, height: Int, bitrate: Int, fps: Int, gopSeconds: Int) -> Bool {
    stop()
    var newSession: VTCompressionSession?
    let status = VTCompressionSessionCreate(
      allocator: kCFAllocatorDefault,
      width: Int32(width),
      height: Int32(height),
      codecType: kCMVideoCodecType_H264,
      encoderSpecification: nil,
      imageBufferAttributes: nil,
      compressedDataAllocator: nil,
      outputCallback: nil,
      refcon: nil,
      compressionSessionOut: &newSession)
    guard status == noErr, let s = newSession else { return false }

    let properties: [CFString: Any] = [
      kVTCompressionPropertyKey_RealTime: true,
      // Baseline decodes everywhere, including older Android MediaCodec decoders.
      kVTCompressionPropertyKey_ProfileLevel: kVTProfileLevel_H264_Baseline_AutoLevel,
      kVTCompressionPropertyKey_AllowFrameReordering: false,
      kVTCompressionPropertyKey_AverageBitRate: bitrate,
      kVTCompressionPropertyKey_ExpectedFrameRate: fps,
      kVTCompressionPropertyKey_MaxKeyFrameInterval: max(1, fps * gopSeconds),
      kVTCompressionPropertyKey_MaxKeyFrameIntervalDuration: gopSeconds,
    ]
    for (key, value) in properties {
      VTSessionSetProperty(s, key: key, value: value as CFTypeRef)
    }
    VTCompressionSessionPrepareToEncodeFrames(s)

    session = s
    self.width = width
    self.height = height
    return true
  }

  /// Encodes one frame and returns every packet produced so far.
  func encode(planes: [PlaneData], timestampUs: Int64) -> [[String: Any]] {
    guard let s = session, let pixelBuffer = makePixelBuffer(planes: planes) else { return [] }
    let pts = CMTime(value: timestampUs, timescale: 1_000_000)

    var frameProperties: CFDictionary?
    if forceKeyframe {
      frameProperties = [kVTEncodeFrameOptionKey_ForceKeyFrame: true] as CFDictionary
      forceKeyframe = false
    }

    VTCompressionSessionEncodeFrame(
      s,
      imageBuffer: pixelBuffer,
      presentationTimeStamp: pts,
      duration: .invalid,
      frameProperties: frameProperties,
      infoFlagsOut: nil
    ) { [weak self] status, _, sampleBuffer in
      guard status == noErr, let sampleBuffer, let self,
        let packet = H264Encoder.annexBPacket(from: sampleBuffer)
      else { return }
      self.pendingLock.lock()
      self.pending.append(packet)
      self.pendingLock.unlock()
    }
    // Realtime, no reordering: flushing this frame adds no meaningful delay.
    VTCompressionSessionCompleteFrames(s, untilPresentationTimeStamp: pts)

    pendingLock.lock()
    defer { pendingLock.unlock() }
    let out = pending
    pending.removeAll()
    return out
  }

  func requestKeyframe() {
    forceKeyframe = true
  }

  func stop() {
    if let s = session {
      VTCompressionSessionCompleteFrames(s, untilPresentationTimeStamp: .invalid)
      VTCompressionSessionInvalidate(s)
    }
    session = nil
    width = 0
    height = 0
    forceKeyframe = false
    pendingLock.lock()
    pending.removeAll()
    pendingLock.unlock()
  }

  // MARK: - Input

  /// Builds an NV12 pixel buffer from NV12 (iOS camera, 2 planes) or
  /// planar/semi-planar YUV420 with explicit strides (3 planes).
  private func makePixelBuffer(planes: [PlaneData]) -> CVPixelBuffer? {
    guard planes.count == 2 || planes.count >= 3 else { return nil }
    var buffer: CVPixelBuffer?
    let attrs: [CFString: Any] = [kCVPixelBufferIOSurfacePropertiesKey: [:] as [CFString: Any]]
    guard
      CVPixelBufferCreate(
        kCFAllocatorDefault, width, height, kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange,
        attrs as CFDictionary, &buffer) == kCVReturnSuccess,
      let pb = buffer
    else { return nil }

    CVPixelBufferLockBaseAddress(pb, [])
    defer { CVPixelBufferUnlockBaseAddress(pb, []) }
    guard let yDst = CVPixelBufferGetBaseAddressOfPlane(pb, 0)?.assumingMemoryBound(to: UInt8.self),
      let uvDst = CVPixelBufferGetBaseAddressOfPlane(pb, 1)?.assumingMemoryBound(to: UInt8.self)
    else { return nil }
    let yDstStride = CVPixelBufferGetBytesPerRowOfPlane(pb, 0)
    let uvDstStride = CVPixelBufferGetBytesPerRowOfPlane(pb, 1)

    copyRows(planes[0], to: yDst, dstStride: yDstStride, rowBytes: width, rows: height)

    if planes.count == 2 {
      // Interleaved CbCr plane: copy rows as-is.
      copyRows(planes[1], to: uvDst, dstStride: uvDstStride, rowBytes: width, rows: height / 2)
    } else {
      // Separate U and V planes: interleave into CbCr.
      let u = planes[1]
      let v = planes[2]
      u.bytes.withUnsafeBytes { uRaw in
        v.bytes.withUnsafeBytes { vRaw in
          let uSrc = uRaw.bindMemory(to: UInt8.self)
          let vSrc = vRaw.bindMemory(to: UInt8.self)
          for row in 0..<(height / 2) {
            let dstRow = uvDst + row * uvDstStride
            for col in 0..<(width / 2) {
              let ui = row * u.rowStride + col * u.pixelStride
              let vi = row * v.rowStride + col * v.pixelStride
              guard ui < uSrc.count, vi < vSrc.count else { continue }
              dstRow[col * 2] = uSrc[ui]
              dstRow[col * 2 + 1] = vSrc[vi]
            }
          }
        }
      }
    }
    return pb
  }

  private func copyRows(_ plane: PlaneData, to dst: UnsafeMutablePointer<UInt8>, dstStride: Int, rowBytes: Int, rows: Int) {
    plane.bytes.withUnsafeBytes { raw in
      guard let src = raw.bindMemory(to: UInt8.self).baseAddress else { return }
      for row in 0..<rows {
        let srcOffset = row * plane.rowStride
        let count = min(rowBytes, max(0, raw.count - srcOffset))
        guard count > 0 else { return }
        memcpy(dst + row * dstStride, src + srcOffset, count)
      }
    }
  }

  // MARK: - Output

  private static let startCode: [UInt8] = [0, 0, 0, 1]

  /// Converts a VideoToolbox (AVCC, length-prefixed) sample to Annex-B.
  static func annexBPacket(from sample: CMSampleBuffer) -> [String: Any]? {
    guard let block = CMSampleBufferGetDataBuffer(sample) else { return nil }
    let attachments = CMSampleBufferGetSampleAttachmentsArray(sample, createIfNecessary: false) as? [[CFString: Any]]
    let notSync = attachments?.first?[kCMSampleAttachmentKey_NotSync] as? Bool ?? false
    let isKeyframe = !notSync

    var out = Data()
    if isKeyframe, let format = CMSampleBufferGetFormatDescription(sample) {
      var count = 0
      CMVideoFormatDescriptionGetH264ParameterSetAtIndex(
        format, parameterSetIndex: 0, parameterSetPointerOut: nil, parameterSetSizeOut: nil,
        parameterSetCountOut: &count, nalUnitHeaderLengthOut: nil)
      for i in 0..<count {
        var pointer: UnsafePointer<UInt8>?
        var size = 0
        if CMVideoFormatDescriptionGetH264ParameterSetAtIndex(
          format, parameterSetIndex: i, parameterSetPointerOut: &pointer, parameterSetSizeOut: &size,
          parameterSetCountOut: nil, nalUnitHeaderLengthOut: nil) == noErr, let pointer
        {
          out.append(contentsOf: startCode)
          out.append(pointer, count: size)
        }
      }
    }

    let total = CMBlockBufferGetDataLength(block)
    var avcc = Data(count: total)
    let copied = avcc.withUnsafeMutableBytes { raw -> OSStatus in
      CMBlockBufferCopyDataBytes(block, atOffset: 0, dataLength: total, destination: raw.baseAddress!)
    }
    guard copied == noErr else { return nil }

    var offset = 0
    while offset + 4 <= avcc.count {
      let length = avcc[offset..<offset + 4].reduce(0) { ($0 << 8) | Int($1) }
      offset += 4
      guard length > 0, offset + length <= avcc.count else { break }
      out.append(contentsOf: startCode)
      out.append(avcc[offset..<offset + length])
      offset += length
    }

    let pts = CMSampleBufferGetPresentationTimeStamp(sample)
    let ptsUs = pts.isValid ? Int64(CMTimeGetSeconds(pts) * 1_000_000) : 0
    return [
      "isKeyframe": isKeyframe,
      "data": FlutterStandardTypedData(bytes: out),
      "ptsUs": ptsUs,
    ]
  }
}
