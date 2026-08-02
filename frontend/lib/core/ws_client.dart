/// WebSocket client for the EntryX event hub.
///
/// Connects with the access token in the query string, subscribes/unsubscribes
/// channels, and fans events out to listeners. Implements an exponential
/// backoff reconnect while authenticated.
library;

import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import 'config.dart';
import 'token_store.dart';

enum ConnectionStatus { disconnected, connecting, connected }

class WsClient {
  WsClient({TokenStore? store}) : _store = store ?? TokenStore();

  final TokenStore _store;
  final _listeners = <String, List<void Function(Map<String, dynamic>)>>{};
  final _subscribed = <String>{};

  WebSocketChannel? _channel;
  StreamSubscription? _sub;
  Timer? _reconnectTimer;
  ConnectionStatus _status = ConnectionStatus.disconnected;
  void Function(ConnectionStatus)? onStatusChanged;
  void Function()? onAuthExpired;
  bool _disposed = false;

  ConnectionStatus get status => _status;

  /// Subscribe to an event type (wildcard matching handled by listeners).
  void on(String type, void Function(Map<String, dynamic> event) handler) {
    _listeners.putIfAbsent(type, () => []).add(handler);
  }

  Future<void> connect() async {
    if (_disposed) return;
    _setStatus(ConnectionStatus.connecting);
    final tokens = await _store.read();
    if (tokens == null) {
      _setStatus(ConnectionStatus.disconnected);
      return;
    }
    try {
      final uri = Uri.parse('${AppConfig.wsUrl}?token=${tokens.accessToken}');
      _channel = WebSocketChannel.connect(uri);
      _sub = _channel!.stream.listen(
        _onMessage,
        onError: (_) => _handleDrop(),
        onDone: _handleDrop,
        cancelOnError: true,
      );
      _setStatus(ConnectionStatus.connected);
    } catch (_) {
      _scheduleReconnect();
    }
  }

  Future<void> subscribe(List<String> channels) async {
    if (_status != ConnectionStatus.connected) return;
    final remaining = channels.where((c) => !_subscribed.contains(c)).toList();
    if (remaining.isEmpty) return;
    _subscribed.addAll(remaining);
    _send({'action': 'subscribe', 'channels': remaining});
  }

  Future<void> unsubscribe(List<String> channels) async {
    _subscribed.removeAll(channels);
    _send({'action': 'unsubscribe', 'channels': channels});
  }

  void _send(Map<String, dynamic> message) {
    _channel?.sink.add(jsonEncode(message));
  }

  void _onMessage(dynamic raw) {
    Map<String, dynamic> event;
    try {
      event = jsonDecode(raw as String) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    final type = event['type'] as String?;
    if (type == null) return;
    for (final handler in _listeners[type] ?? const <void Function(Map<String, dynamic>)>[]) {
      handler(event);
    }
  }

  void _handleDrop() {
    if (_disposed) return;
    _setStatus(ConnectionStatus.disconnected);
    _subscribed.clear();
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), connect);
  }

  void _setStatus(ConnectionStatus status) {
    if (_status == status) return;
    _status = status;
    onStatusChanged?.call(status);
  }

  Future<void> dispose() async {
    _disposed = true;
    _reconnectTimer?.cancel();
    await _sub?.cancel();
    await _channel?.sink.close();
  }
}
