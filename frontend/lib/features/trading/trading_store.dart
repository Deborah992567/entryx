/// Trading Terminal store: account, positions, pending orders, and history.
///
/// Loads each section via REST, then keeps them fresh through the WebSocket
/// (`account.<id>`, `orders`, `positions`, `history` events). Any trading event
/// triggers a reload so the tabs always mirror the broker state. Nothing is
/// invented locally — all values come from the backend.
library;

import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../core/ws_client.dart';
import '../auth/auth_store.dart';
import 'trading_models.dart';

class TradingStore extends ChangeNotifier {
  TradingStore({
    required ApiClient api,
    required WsClient ws,
    AuthStore? auth,
    int? userId,
  })  : _api = api,
        _ws = ws,
        _auth = auth,
        _userIdOverride = userId {
    for (final type in _eventTypes) {
      _ws.on(type, (_) => refresh());
    }
    _ws.addStatusListener(_onStatusChanged);
    _auth?.addListener(_maybeSubscribeAccount);
    _maybeSubscribeAccount();
    refresh();
  }

  static const _eventTypes = [
    'account.updated',
    'order.created',
    'order.updated',
    'order.cancelled',
    'order.expired',
    'order.filled',
    'position.opened',
    'position.updated',
    'position.closed',
    'trade.closed',
  ];

  final ApiClient _api;
  final WsClient _ws;
  final AuthStore? _auth;
  final int? _userIdOverride;

  int? get _userId => _userIdOverride ?? _auth?.user?.id;

  TradingAccount? _account;
  List<TradingPosition> _positions = const [];
  List<TradingOrder> _orders = const [];
  List<TradeRecord> _history = const [];
  bool _loading = true;
  String _error = '';

  TradingAccount? get account => _account;
  List<TradingPosition> get positions => _positions;
  List<TradingOrder> get orders => _orders;
  List<TradeRecord> get history => _history;
  bool get loading => _loading;
  String get error => _error;
  bool get connected => _ws.status == ConnectionStatus.connected;

  void _maybeSubscribeAccount() {
    final userId = _userId;
    if (userId == null) return;
    _ws.subscribe(['account.$userId', 'orders', 'positions', 'history']);
  }

  void _onStatusChanged(ConnectionStatus status) {
    if (status == ConnectionStatus.connected) {
      _maybeSubscribeAccount();
      refresh();
    }
    notifyListeners();
  }

  Future<void> refresh() async {
    _loading = true;
    notifyListeners();
    try {
      final accountData = await _api.get('/trading/account') as Map<String, dynamic>;
      final positionsData = await _api.get('/trading/positions') as List<dynamic>;
      final ordersData = await _api.get('/trading/orders') as List<dynamic>;
      final historyData = await _api.get('/trading/history') as List<dynamic>;
      _account = TradingAccount.fromJson(accountData);
      _positions = positionsData
          .map((e) => TradingPosition.fromJson(e as Map<String, dynamic>))
          .toList();
      _orders = ordersData
          .map((e) => TradingOrder.fromJson(e as Map<String, dynamic>))
          .toList();
      _history = historyData
          .map((e) => TradeRecord.fromJson(e as Map<String, dynamic>))
          .toList()
          .reversed
          .toList();
      if (_error.isNotEmpty) _error = '';
    } catch (e) {
      _error = 'Trading data unavailable: $e';
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<void> cancelOrder(String orderId) async {
    try {
      await _api.delete('/trading/orders/$orderId');
      await refresh();
    } catch (e) {
      _error = 'Failed to cancel order: $e';
      notifyListeners();
    }
  }

  Future<void> closePosition(String positionId) async {
    try {
      await _api.delete('/trading/positions/$positionId');
      await refresh();
    } catch (e) {
      _error = 'Failed to close position: $e';
      notifyListeners();
    }
  }

  Future<void> partialClose(String positionId, double volume) async {
    try {
      await _api.post('/trading/positions/$positionId/close', body: {'volume': volume});
      await refresh();
    } catch (e) {
      _error = 'Failed to partially close: $e';
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _auth?.removeListener(_maybeSubscribeAccount);
    super.dispose();
  }
}
