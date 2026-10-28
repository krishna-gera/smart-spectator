import 'dart:typed_data';

import 'packet_encoder.dart';

/// Thrown when an incoming packet violates SS-DOC-005.
class PacketProtocolException implements Exception {
  final String message;
  PacketProtocolException(this.message);

  @override
  String toString() => 'PacketProtocolException: $message';
}

class PacketHeader {
  final int frameType;
  final int sequenceNumber;
  final int ptsUs;
  final int payloadLength;

  const PacketHeader({
    required this.frameType,
    required this.sequenceNumber,
    required this.ptsUs,
    required this.payloadLength,
  });

  bool get isKeyframe => frameType == PacketEncoder.frameTypeIdr;
}

class DecodedPacket {
  final PacketHeader header;
  final Uint8List payload;

  const DecodedPacket(this.header, this.payload);
}

/// Smart Spectator - 24-Byte Camera Binary Framing Protocol (decode side).
class PacketDecoder {
  /// Upper bound on a single packet payload to prevent memory exhaustion.
  static const int maxPayloadBytes = 10 * 1024 * 1024;

  static PacketHeader decodeHeader(Uint8List bytes) {
    if (bytes.length < PacketEncoder.headerSizeBytes) {
      throw PacketProtocolException(
          'Header too short: expected ${PacketEncoder.headerSizeBytes} bytes, got ${bytes.length}');
    }
    final view = ByteData.sublistView(bytes, 0, PacketEncoder.headerSizeBytes);

    final magic = view.getUint16(0, Endian.big);
    if (magic != PacketEncoder.magicBytes) {
      throw PacketProtocolException('Invalid magic bytes: 0x${magic.toRadixString(16)}');
    }
    final version = view.getUint8(2);
    if (version != PacketEncoder.protocolVersion) {
      throw PacketProtocolException('Unsupported protocol version: $version');
    }
    final crc = view.getUint16(22, Endian.big);
    final expectedCrc = PacketEncoder.computeCrc16(Uint8List.sublistView(bytes, 0, 22));
    if (crc != expectedCrc) {
      throw PacketProtocolException('CRC16 checksum mismatch');
    }
    final payloadLength = view.getUint32(16, Endian.big);
    if (payloadLength > maxPayloadBytes) {
      throw PacketProtocolException('Oversized payload length rejected: $payloadLength bytes');
    }

    return PacketHeader(
      frameType: view.getUint8(3),
      sequenceNumber: view.getUint32(4, Endian.big),
      ptsUs: view.getUint64(8, Endian.big),
      payloadLength: payloadLength,
    );
  }

  /// Decodes one complete packet (one WebSocket binary message).
  static DecodedPacket decode(Uint8List bytes) {
    final header = decodeHeader(bytes);
    final end = PacketEncoder.headerSizeBytes + header.payloadLength;
    if (bytes.length < end) {
      throw PacketProtocolException(
          'Truncated payload: expected ${header.payloadLength} bytes, got ${bytes.length - PacketEncoder.headerSizeBytes}');
    }
    return DecodedPacket(
      header,
      Uint8List.sublistView(bytes, PacketEncoder.headerSizeBytes, end),
    );
  }
}
