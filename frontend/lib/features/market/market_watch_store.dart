/// Market Watch store: symbols, live quotes, search/favorites/categories.
///
/// Loads the symbol catalog via REST, then subscribes to `market.watch` over
/// the WebSocket to receive `market.snapshot` and per-symbol `market.tick`
/// updates. Values only ever come from the backend — nothing is invented here.
library;

import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../core/models.dart';
import '../../core/ws_client.dart';

class MarketWatchStore extends ChangeNotifier {
  MarketWatchStore({required ApiClient api, required WsClient ws})
      : _api = api,
        _ws = ws {
    _ws.on('market.snapshot', _onSnapshot);
    _ws.on('market.tick', _onTick);
    _ws.onStatusChanged = _onStatusChanged;
    _loadSymbols();
    _ws.subscribe(const ['market.watch']);
  }

  final ApiClient _api;
  final WsClient _ws;

  List<SymbolInfo> _symbols = const [];
  final Map<String, Quote> _quotes = {};
  final Set<String> _favorites = {};
  String _query = '';
  String _category = 'all';
  String _error = '';

  List<SymbolInfo> get symbols => _symbols;
  Map<String, Quote> get quotes => _quotes;
  Set<String> get favorites => _favorites;
  String get query => _query;
  String get category => _category;
  String get error => _error;
  bool get connected => _ws.status == ConnectionStatus.connected;

  List<String> get categories {
    final cats = <String>{'all'};
    for (final s in _symbols) {
      cats.add(s.category);
    }
    return cats.toList()..sort();
  }

  bool isFavorite(String symbol) => _favorites.contains(symbol);

  void toggleFavorite(String symbol) {
    if (!_favorites.add(symbol)) {
      _favorites.remove(symbol);
    }
    notifyListeners();
  }

  void setQuery(String value) {
    _query = value;
    notifyListeners();
  }

  void setCategory(String value) {
    _category = value;
    notifyListeners();
  }

  Quote? quoteFor(String symbol) => _quotes[symbol];

  /// Rows matching the current query and category filter.
  List<SymbolInfo> get visibleSymbols {
    final q = _query.trim().toUpperCase();
    return _symbols.where((s) {
      if (_category != 'all' && s.category != _category) return false;
      if (q.isEmpty) return true;
      return s.symbol.contains(q) || s.name.toUpperCase().contains(q);
    }).toList();
  }

  Future<void> _loadSymbols() async {
    try {
      final data = await _api.get('/market/symbols') as List<dynamic>;
      _symbols = data
          .map((e) => SymbolInfo.fromJson(e as Map<String, dynamic>))
          .toList();
      if (_error.isNotEmpty) _error = '';
      notifyListeners();
    } catch (e) {
      _error = 'Failed to load symbols: $e';
      notifyListeners();
    }
  }

  void _onSnapshot(Map<String, dynamic> event) {
    final data = event['data'];
    if (data is! List) return;
    for (final item in data) {
      if (item is Map<String, dynamic>) {
        _applyQuote(Quote.fromJson(item));
      }
    }
    notifyListeners();
  }

  void _onTick(Map<String, dynamic> event) {
    final data = event['data'];
    if (data is Map<String, dynamic>) {
      _applyQuote(Quote.fromJson(data));
      notifyListeners();
    }
  }

  void _applyQuote(Quote quote) {
    if (quote.symbol.isEmpty) return;
    _quotes[quote.symbol] = quote;
  }

  void _onStatusChanged(ConnectionStatus status) {
    if (status == ConnectionStatus.connected) {
      _ws.subscribe(const ['market.watch']);
    }
    notifyListeners();
  }
}
