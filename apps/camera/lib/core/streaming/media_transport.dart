"""
Smart Spectator - Media Transport & Reconnect State Machine
Conforms to Sections 6, 7, 8, 11 of Phase 6 Master Specification.
Enforces exponential backoff: 1s, 2s, 4s, 8s, 16s, up to 30s max, resetting on connection.
"""

import 'dart:async';
import 'dart:math';
import 'dart:typed_data';
import 'package:web_socket_channel/web_socket_channel.dart';

enum TransportStatus {
  disconnected,
  connecting,
  connected,
  reconnecting,
  failed,
}

class MediaTransport {
  final String hubIp;
  final int hubPort;
  final String cameraId;
  final String deviceToken;
  final int maxReconnectAttempts;
  final int maxBackoffSeconds;

  WebSocketChannel? _channel;
  TransportStatus _status = TransportStatus.disconnected;
  final _statusController = StreamController<TransportStatus>.broadcast();
  bool _shouldReconnect = false;
  int _reconnectAttempts = 0;
  Timer? _reconnectTimer;

  MediaTransport({
    required this.hubIp,
    required this.hubPort,
    required this.cameraId,
    required this.deviceToken,
    this.maxReconnectAttempts = 10,
    this.maxBackoffSeconds = 30,
  });

  Stream<TransportStatus> get statusStream => _statusController.stream;
  TransportStatus get status => _status;
  int get reconnectAttempts => _reconnectAttempts;

  Future<void> connect() async {
    _shouldReconnect = true;
    _reconnectAttempts = 0;
    _reconnectTimer?.cancel();
    await _doConnect();
  }

  Future<void> _doConnect() async {
    _updateStatus(TransportStatus.connecting);

    // Primary connection URL
    final wsUrl = Uri.parse(
      'ws://$hubIp:$hubPort/api/v1/streams/ingest/$cameraId?token=$deviceToken'
    );

    try {
      _channel = WebSocketChannel.connect(wsUrl);
      await _channel!.ready;
      _updateStatus(TransportStatus.connected);
      // Reset backoff counter on successful handshake (Section 7)
      _reconnectAttempts = 0;

      _channel!.stream.listen(
        (message) {
          // Inbound control frames if any
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

    if (_reconnectAttempts >= maxReconnectAttempts) {
      // Reconnect limit exceeded -> FAILED state (Section 7)
      _updateStatus(TransportStatus.failed);
      return;
    }

    _updateStatus(TransportStatus.reconnecting);
    _reconnectAttempts++;

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, up to maxBackoffSeconds (Section 7)
    final backoffSeconds = min(
      maxBackoffSeconds,
      pow(2, _reconnectAttempts - 1).toInt(),
    );

    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(Duration(seconds: backoffSeconds), () {
      if (_shouldReconnect) {
        _doConnect();
      }
    });
  }

  void disconnect() {
    _shouldReconnect = false;
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
    _updateStatus(TransportStatus.disconnected);
  }

  void _updateStatus(TransportStatus newStatus) {
    _status = newStatus;
    if (!_statusController.isClosed) {
      _statusController.add(_status);
    }
  }

  void dispose() {
    disconnect();
    _statusController.close();
  }
}
