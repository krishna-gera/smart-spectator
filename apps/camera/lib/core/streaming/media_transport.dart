import 'dart:async';
import 'dart:typed_data';
import 'package:web_socket_channel/web_socket_channel.dart';

enum TransportStatus {
  disconnected,
  connecting,
  connected,
  reconnecting,
  error,
}

class MediaTransport {
  final String hubIp;
  final int hubPort;
  final String cameraId;
  final String deviceToken;
  
  WebSocketChannel? _channel;
  TransportStatus _status = TransportStatus.disconnected;
  final _statusController = StreamController<TransportStatus>.broadcast();
  bool _shouldReconnect = false;
  int _reconnectAttempts = 0;

  MediaTransport({
    required this.hubIp,
    required this.hubPort,
    required this.cameraId,
    required this.deviceToken,
  });

  Stream<TransportStatus> get statusStream => _statusController.stream;
  TransportStatus get status => _status;

  Future<void> connect() async {
    _shouldReconnect = true;
    _reconnectAttempts = 0;
    await _doConnect();
  }

  Future<void> _doConnect() async {
    _updateStatus(TransportStatus.connecting);
    final wsUrl = Uri.parse(
      'ws://$hubIp:$hubPort/api/v1/streams/ingest/$cameraId?token=$deviceToken'
    );

    try {
      _channel = WebSocketChannel.connect(wsUrl);
      await _channel!.ready;
      _updateStatus(TransportStatus.connected);
      _reconnectAttempts = 0;

      _channel!.stream.listen(
        (message) {
          // Inbound messages if any
        },
        onDone: () {
          _handleDisconnect();
        },
        onError: (error) {
          _handleDisconnect();
        },
        cancelOnError: true,
      );
    } catch (e) {
      _handleDisconnect();
    }
  }

  void sendPacket(Uint8List packetBytes) {
    if (_status == TransportStatus.connected && _channel != null) {
      try {
        _channel!.sink.add(packetBytes);
      } catch (e) {
        _handleDisconnect();
      }
    }
  }

  void _handleDisconnect() {
    _channel = null;
    if (!_shouldReconnect) {
      _updateStatus(TransportStatus.disconnected);
      return;
    }

    _updateStatus(TransportStatus.reconnecting);
    _reconnectAttempts++;
    final delaySeconds = (_reconnectAttempts > 5) ? 10 : (1 << _reconnectAttempts); // Exponential backoff

    Timer(Duration(seconds: delaySeconds), () {
      if (_shouldReconnect) {
        _doConnect();
      }
    });
  }

  void disconnect() {
    _shouldReconnect = false;
    _channel?.sink.close();
    _channel = null;
    _updateStatus(TransportStatus.disconnected);
  }

  void _updateStatus(TransportStatus newStatus) {
    _status = newStatus;
    _statusController.add(_status);
  }

  void dispose() {
    disconnect();
    _statusController.close();
  }
}
