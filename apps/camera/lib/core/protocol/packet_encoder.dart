import 'dart:typed_data';

/// Smart Spectator - 24-Byte Camera Binary Framing Protocol
/// Implements SS-DOC-005 in Dart for Android Camera Nodes.
class PacketEncoder {
  static const int magicBytes = 0x5353; // 'SS'
  static const int protocolVersion = 0x01;
  static const int headerSizeBytes = 24;

  // Frame Types
  static const int frameTypeIdr = 0x01;
  static const int frameTypeP = 0x02;
  static const int frameTypeB = 0x03;
  static const int frameTypeAudio = 0x04;

  /// Computes CRC-16-CCITT (Poly: 0x1021, Init: 0xFFFF)
  static int computeCrc16(Uint8List data) {
    int crc = 0xFFFF;
    for (int byte in data) {
      crc ^= (byte << 8);
      for (int i = 0; i < 8; i++) {
        if ((crc & 0x8000) != 0) {
          crc = ((crc << 1) ^ 0x1021) & 0xFFFF;
        } else {
          crc = (crc << 1) & 0xFFFF;
        }
      }
    }
    return crc;
  }

  /// Encodes an H.264 NAL unit into a 24-byte header packet.
  static Uint8List encodePacket({
    required int frameType,
    required int sequenceNumber,
    required int ptsUs,
    required Uint8List payload,
  }) {
    final payloadLength = payload.length;
    final headerPre = Uint8List(22);
    final bdata = ByteData.sublistView(headerPre);

    // Big-endian formatting strictly conforming to SS-DOC-005
    bdata.setUint16(0, magicBytes, Endian.big);
    bdata.setUint8(2, protocolVersion);
    bdata.setUint8(3, frameType);
    bdata.setUint32(4, sequenceNumber, Endian.big);
    bdata.setUint64(8, ptsUs, Endian.big);
    bdata.setUint32(16, payloadLength, Endian.big);
    bdata.setUint16(20, 0x0000, Endian.big); // Reserved

    final crc16 = computeCrc16(headerPre);

    final fullPacket = Uint8List(headerSizeBytes + payloadLength);
    fullPacket.setRange(0, 22, headerPre);
    
    // Set CRC16 at offset 22
    final fullView = ByteData.sublistView(fullPacket);
    fullView.setUint16(22, crc16, Endian.big);

    // Append payload
    fullPacket.setRange(24, 24 + payloadLength, payload);

    return fullPacket;
  }
}
