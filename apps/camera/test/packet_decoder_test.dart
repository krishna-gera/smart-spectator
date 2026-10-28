import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:smart_spectator_camera/core/protocol/packet_decoder.dart';
import 'package:smart_spectator_camera/core/protocol/packet_encoder.dart';

void main() {
  Uint8List packet({int frameType = PacketEncoder.frameTypeIdr, int seq = 7, List<int> payload = const [0, 0, 0, 1, 0x65]}) =>
      PacketEncoder.encodePacket(
        frameType: frameType,
        sequenceNumber: seq,
        ptsUs: 1234567890123,
        payload: Uint8List.fromList(payload),
      );

  test('decodes what the camera encoder produces', () {
    final decoded = PacketDecoder.decode(packet());
    expect(decoded.header.isKeyframe, isTrue);
    expect(decoded.header.sequenceNumber, 7);
    expect(decoded.header.ptsUs, 1234567890123);
    expect(decoded.payload, [0, 0, 0, 1, 0x65]);
  });

  test('uses CRC-16-CCITT for the header checksum', () {
    // CRC-16-CCITT (0x1021, init 0xFFFF), the checksum used by the 24-byte packet header:
    // the standard check value for "123456789" is 0x29B1.
    expect(PacketEncoder.computeCrc16(Uint8List.fromList('123456789'.codeUnits)), 0x29B1);
  });

  test('rejects a corrupted header', () {
    final bytes = packet();
    bytes[5] ^= 0xFF; // flip sequence number bits, CRC no longer matches
    expect(() => PacketDecoder.decode(bytes), throwsA(isA<PacketProtocolException>()));
  });

  test('rejects wrong magic bytes', () {
    final bytes = packet();
    bytes[0] = 0x00;
    expect(() => PacketDecoder.decode(bytes), throwsA(isA<PacketProtocolException>()));
  });

  test('rejects a truncated payload', () {
    final bytes = packet(payload: List.filled(100, 1));
    expect(() => PacketDecoder.decode(Uint8List.sublistView(bytes, 0, 60)), throwsA(isA<PacketProtocolException>()));
  });

  test('rejects a short header', () {
    expect(() => PacketDecoder.decode(Uint8List(10)), throwsA(isA<PacketProtocolException>()));
  });
}
