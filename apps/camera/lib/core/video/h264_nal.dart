import 'dart:typed_data';

/// Minimal H.264 Annex-B inspection (mirrors H264 in VideoEncoder.kt).
class H264Nal {
  static const int idrSlice = 5;
  static const int sps = 7;
  static const int pps = 8;

  /// NAL unit types following each 00 00 01 start code.
  static List<int> types(Uint8List data) {
    final types = <int>[];
    for (var i = 0; i + 3 < data.length; i++) {
      if (data[i] == 0 && data[i + 1] == 0 && data[i + 2] == 1) {
        types.add(data[i + 3] & 0x1F);
        i += 2;
      }
    }
    return types;
  }

  /// True when a decoder can start from this packet (has SPS and an IDR slice).
  static bool isDecoderEntryPoint(Uint8List data) {
    final t = types(data);
    return t.contains(sps) && t.contains(idrSlice);
  }
}
