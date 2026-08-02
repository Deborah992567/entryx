/// System status store: health polling + WebSocket connection state.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../core/models.dart';
import '../../core/ws_client.dart';

class SystemStatusStore extends ChangeNotifier {
  SystemStatusStore({required ApiClient api, required WsClient ws})
      : _api = api,
        _ws = ws {
    _ws.onStatusChanged = (_) => notifyListeners();
  }

  final ApiClient _api;
  final WsClient _ws;

  Health? _health;
  ConnectionStatus _wsStatus = ConnectionStatus.disconnected;
  Timer? _pollTimer;

  Health? get health => _health;
  ConnectionStatus get wsStatus => _wsStatus;

  /// True when backend is reachable.
  bool get backendUp => _health != null;

  void start() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 10), (_) => refresh());
    refresh();
  }

  Future<void> refresh() async {
    try {
      _health = await _api.health();
    } catch (_) {
      _health = null;
    }
    _wsStatus = _ws.status;
    notifyListeners();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}
