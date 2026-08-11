/// Chart store: candle series, viewport (zoom/pan/follow), crosshair, overlays.
///
/// Loads candles via REST (`/market/candles`), subscribes to the live
/// `candles.<symbol>.<tf>` channel for forming-bar updates, and computes the
/// enabled indicator overlays. The viewport always follows the newest bar until
/// the user pans back; panning past the newest bar snaps back to follow mode.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../core/ws_client.dart';
import '../backtest/backtest_models.dart';
import 'chart_models.dart';
import 'chart_template.dart';
import 'indicator_engine.dart';

class ChartStore extends ChangeNotifier {
  ChartStore({
    required ApiClient api,
    required WsClient ws,
    String symbol = 'XAUUSD',
    Timeframe timeframe = Timeframe.h1,
  })  : _api = api,
        _ws = ws,
        _symbol = symbol,
        _timeframe = timeframe {
    _ws.on('market.candle', _onCandle);
    _ws.addStatusListener(_onStatusChanged);
    _subscribeCandleChannel();
    _load();
  }

  final ApiClient _api;
  final WsClient _ws;

  static const int minBars = 20;
  static const int maxBars = 500;
  static const int defaultBars = 140;

  String _symbol;
  Timeframe _timeframe;
  List<ChartCandle> _candles = const [];
  String _error = '';
  bool _loading = true;
  int _barsVisible = defaultBars;
  int _right = -1; // -1 = follow the newest bar
  int? _crosshairIndex;
  double? _crosshairPrice;
  ChartTemplate _template = ChartTemplate.dark;

  List<ChartDrawing> _drawings = [];
  int? _selectedDrawingId;
  int _nextDrawingId = 1;
  DrawingTool _tool = DrawingTool.select;
  Timer? _saveTimer;
  ChartSyncGroup? _sync;
  bool _disposed = false;

  BacktestResult? _backtest;
  List<double?> _equitySeries = const [];
  List<TradeMarker> _backtestMarkers = const [];

  static const List<String> _indicatorOrder = ['sma20', 'sma50', 'ema20', 'vwap', 'bollinger'];
  final Map<String, bool> _indicatorEnabled = {
    'sma20': true,
    'sma50': true,
    'ema20': false,
    'vwap': false,
    'bollinger': false,
  };

  String get symbol => _symbol;
  Timeframe get timeframe => _timeframe;
  ChartTemplate get template => _template;
  List<ChartCandle> get candles => _candles;
  bool get loading => _loading;
  String get error => _error;
  int get barsVisible => _barsVisible;
  int? get crosshairIndex => _crosshairIndex;
  double? get crosshairPrice => _crosshairPrice;
  bool get followingLatest => _right == -1;
  bool get hasData => _candles.isNotEmpty;
  bool get synced => _sync != null;
  BacktestResult? get backtest => _backtest;
  List<double?> get equitySeries => _equitySeries;
  List<TradeMarker> get backtestMarkers => _backtestMarkers;

  /// The right edge (in bar index terms, -1 = follow) shared with synced charts.
  int get syncRight => _right;

  /// Joins or leaves a chart sync group.
  void setSyncGroup(ChartSyncGroup? group) {
    if (identical(_sync, group)) return;
    _sync?.leave(this);
    _sync = group;
    group?.join(this);
    notifyListeners();
  }

  /// Applies a viewport pushed from another synced chart (no re-broadcast).
  void applySyncedViewport(int right, int barsVisible) {
    if (_right == right && _barsVisible == barsVisible) return;
    _right = right;
    _barsVisible = barsVisible;
    _crosshairIndex = null;
    _crosshairPrice = null;
    notifyListeners();
  }

  /// Applies a crosshair pushed from another synced chart (no re-broadcast).
  void applySyncedCrosshair(int? index, double? price) {
    if (_crosshairIndex == index && _crosshairPrice == price) return;
    _crosshairIndex = index;
    _crosshairPrice = price;
    notifyListeners();
  }

  List<String> get indicatorKeys => List.unmodifiable(_indicatorOrder);
  bool indicatorEnabled(String key) => _indicatorEnabled[key] ?? false;

  List<ChartDrawing> get drawings => List.unmodifiable(_drawings);
  int? get selectedDrawingId => _selectedDrawingId;
  int get nextDrawingId => _nextDrawingId;
  @visibleForTesting
  ApiClient get api => _api;
  DrawingTool get tool => _tool;
  ChartDrawing? get selectedDrawing {
    if (_selectedDrawingId == null) return null;
    for (final d in _drawings) {
      if (d.id == _selectedDrawingId) return d;
    }
    return null;
  }

  int get _viewEnd => _right == -1 ? _candles.length : _right + 1;

  int get visibleStart {
    final start = _viewEnd - _barsVisible;
    return start < 0 ? 0 : start;
  }

  int get visibleEnd {
    final end = _viewEnd;
    return end > _candles.length ? _candles.length : end;
  }

  /// Index of the crosshair candle's bar or the rightmost visible bar.
  int? get activeBarIndex {
    if (_candles.isEmpty) return null;
    final idx = _crosshairIndex ?? visibleEnd - 1;
    return idx;
  }

  Future<void> setSymbol(String symbol) async {
    if (symbol == _symbol || symbol.isEmpty) return;
    _symbol = symbol;
    _drawings = [];
    _selectedDrawingId = null;
    _nextDrawingId = 1;
    _resetView();
    _subscribeCandleChannel();
    await _load();
  }

  Future<void> setTimeframe(Timeframe tf) async {
    if (tf == _timeframe) return;
    _timeframe = tf;
    _drawings = [];
    _selectedDrawingId = null;
    _nextDrawingId = 1;
    _resetView();
    _subscribeCandleChannel();
    await _load();
  }

  void toggleIndicator(String key) {
    if (!_indicatorEnabled.containsKey(key)) return;
    _indicatorEnabled[key] = !(_indicatorEnabled[key] ?? false);
    notifyListeners();
  }

  void setTemplate(ChartTemplate template) {
    if (identical(_template, template) || _template.id == template.id) return;
    _template = template;
    notifyListeners();
  }

  /// Drag delta in bars; positive (drag right) moves the view toward older bars.
  void panBy(int deltaBars) {
    if (_candles.isEmpty || deltaBars == 0) return;
    var next = _right == -1 ? _candles.length - 1 : _right;
    next -= deltaBars;
    if (next >= _candles.length - 1) {
      _right = -1;
    } else if (next < _barsVisible - 1) {
      _right = _barsVisible - 1;
    } else {
      _right = next;
    }
    _crosshairIndex = null;
    _crosshairPrice = null;
    notifyListeners();
    _sync?.onViewportChanged(this);
  }

  void zoomBy(double factor) {
    var bars = (_barsVisible / factor).round();
    bars = bars < minBars ? minBars : (bars > maxBars ? maxBars : bars);
    if (bars == _barsVisible) return;
    _barsVisible = bars;
    _crosshairIndex = null;
    _crosshairPrice = null;
    notifyListeners();
    _sync?.onViewportChanged(this);
  }

  void zoomIn() => zoomBy(1.25);

  void zoomOut() => zoomBy(1 / 1.25);

  void resetView() {
    _right = -1;
    _barsVisible = defaultBars;
    _crosshairIndex = null;
    _crosshairPrice = null;
    notifyListeners();
    _sync?.onViewportChanged(this);
  }

  void setCrosshair(int? index, double? price) {
    if (_crosshairIndex == index && _crosshairPrice == price) return;
    _crosshairIndex = index;
    _crosshairPrice = price;
    notifyListeners();
    _sync?.onCrosshairChanged(this);
  }

  /// Allocates an id and appends a finished drawing.
  void addDrawing(ChartDrawing drawing) {
    _drawings = [..._drawings, drawing];
    if (drawing.id >= _nextDrawingId) {
      _nextDrawingId = drawing.id + 1;
    }
    _scheduleSave();
    notifyListeners();
  }

  void updateDrawing(ChartDrawing drawing) {
    _drawings = [
      for (final d in _drawings) d.id == drawing.id ? drawing : d,
    ];
    _scheduleSave();
    notifyListeners();
  }

  void removeDrawing(int id) {
    _drawings = [for (final d in _drawings) if (d.id != id) d];
    if (_selectedDrawingId == id) {
      _selectedDrawingId = null;
    }
    _scheduleSave();
    notifyListeners();
  }

  void removeSelectedDrawing() {
    final id = _selectedDrawingId;
    if (id != null) removeDrawing(id);
  }

  void clearDrawings() {
    _drawings = [];
    _selectedDrawingId = null;
    _scheduleSave();
    notifyListeners();
  }

  void selectDrawing(int? id) {
    if (_selectedDrawingId == id) return;
    _selectedDrawingId = id;
    notifyListeners();
  }

  void setTool(DrawingTool tool) {
    if (_tool == tool) return;
    _tool = tool;
    if (tool != DrawingTool.select) {
      _selectedDrawingId = null;
    }
    notifyListeners();
  }

  /// Rebuilds overlays for the current indicator config.
  IndicatorPack buildIndicators() {
    final overlays = <Overlay>[];
    final bands = <Bands>[];
    if (_candles.isEmpty) return IndicatorPack(overlays: overlays, bands: bands);
    final closeList = _candles.map((c) => c.c).toList();
    if (indicatorEnabled('sma20')) {
      overlays.add(Overlay(label: 'SMA 20', series: sma(closeList, 20)));
    }
    if (indicatorEnabled('sma50')) {
      overlays.add(Overlay(label: 'SMA 50', series: sma(closeList, 50)));
    }
    if (indicatorEnabled('ema20')) {
      overlays.add(Overlay(label: 'EMA 20', series: ema(closeList, 20)));
    }
    if (indicatorEnabled('vwap')) {
      overlays.add(Overlay(label: 'VWAP', series: vwap(_candles)));
    }
    if (indicatorEnabled('bollinger')) {
      final bb = bollinger(_candles);
      bands.add(Bands(label: 'BB 20,2', mid: bb.mid, upper: bb.upper, lower: bb.lower));
    }
    return IndicatorPack(overlays: overlays, bands: bands);
  }

  Future<void> refresh() => _load();

  /// Overlays a completed backtest result: its equity curve fills the equity
  /// pane and each trade is anchored with entry/exit markers by candle
  /// timestamp (so the overlay lines up regardless of the chart's bar count).
  void setBacktest(BacktestResult result) {
    _backtest = result;
    _mapBacktestOverlay();
    notifyListeners();
  }

  void clearBacktest() {
    _backtest = null;
    _equitySeries = const [];
    _backtestMarkers = const [];
    notifyListeners();
  }

  void _mapBacktestOverlay() {
    final result = _backtest;
    _equitySeries = const [];
    _backtestMarkers = const [];
    if (result == null || _candles.isEmpty) return;
    final indexByTs = <int, int>{};
    for (var i = 0; i < _candles.length; i++) {
      indexByTs[_candles[i].ts.toUtc().millisecondsSinceEpoch] = i;
    }
    final equity = List<double?>.filled(_candles.length, null);
    for (final p in result.equityCurve) {
      final idx = indexByTs[p.ts.toUtc().millisecondsSinceEpoch];
      if (idx != null) equity[idx] = p.equity;
    }
    final markers = <TradeMarker>[];
    for (final t in result.trades) {
      final openIdx = indexByTs[DateTime.parse(t.openedAt).toUtc().millisecondsSinceEpoch];
      final closeIdx = indexByTs[DateTime.parse(t.closedAt).toUtc().millisecondsSinceEpoch];
      final buy = t.side == 'buy';
      if (openIdx != null) {
        markers.add(TradeMarker(
            bar: openIdx, price: t.openPrice, kind: TradeMarkerKind.entry, buy: buy));
      }
      if (closeIdx != null) {
        markers.add(TradeMarker(
            bar: closeIdx, price: t.closePrice, kind: TradeMarkerKind.exit, buy: buy));
      }
    }
    _equitySeries = equity;
    _backtestMarkers = markers;
  }

  @override
  void dispose() {
    _disposed = true;
    _saveTimer?.cancel();
    _sync?.leave(this);
    super.dispose();
  }

  /// Reloads only when the store has no usable data yet (e.g. raced auth).
  Future<void> refreshIfNeeded() async {
    if (!_loading && _error.isNotEmpty) {
      await _load();
    }
  }

  void _resetView() {
    _right = -1;
    _barsVisible = defaultBars;
    _crosshairIndex = null;
    _crosshairPrice = null;
    _candles = const [];
    _error = '';
    _backtest = null;
    _equitySeries = const [];
    _backtestMarkers = const [];
  }

  void _subscribeCandleChannel() {
    _ws.subscribe(['candles.$_symbol.${_timeframe.api}']);
  }

  Future<void> _load() async {
    _loading = true;
    _error = '';
    notifyListeners();
    try {
      final data = await _api
          .get('/market/candles?symbol=$_symbol&tf=${_timeframe.api}&limit=500') as List<dynamic>;
      if (_disposed) return;
      _candles = data
          .map((e) => ChartCandle.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
      _right = -1;
      await _loadDrawings();
      if (_disposed) return;
      notifyListeners();
    } catch (e) {
      if (_disposed) return;
      _error = 'Failed to load candles: $e';
      notifyListeners();
    } finally {
      if (!_disposed) {
        _loading = false;
        notifyListeners();
      }
    }
  }

  /// Restores drawings for the current symbol/timeframe from the server.
  Future<void> _loadDrawings() async {
    try {
      final data = await _api.get(
          '/workspace/drawings?symbol=$_symbol&timeframe=${_timeframe.api}') as List<dynamic>;
      final loaded = <ChartDrawing>[];
      var maxId = 0;
      for (final e in data) {
        final d = chartDrawingFromJson(
            (e as Map<String, dynamic>)['points_json'] as Map<String, dynamic>);
        loaded.add(d);
        if (d.id > maxId) maxId = d.id;
      }
      _drawings = loaded;
      _nextDrawingId = maxId + 1;
      notifyListeners();
    } catch (_) {
      // keep whatever is currently in memory
    }
  }

  /// Debounces a full-chart save of the current drawings.
  ///
  /// The drawing set is snapshotted at schedule time so a pending save is not
  /// corrupted if the user switches symbol/timeframe before it fires.
  void _scheduleSave() {
    _saveTimer?.cancel();
    final symbol = _symbol;
    final timeframe = _timeframe.api;
    final snapshot = List<ChartDrawing>.of(_drawings);
    _saveTimer = Timer(const Duration(milliseconds: 400), () {
      _persistDrawings(symbol: symbol, timeframe: timeframe, drawings: snapshot);
    });
  }

  Future<void> _persistDrawings({
    required String symbol,
    required String timeframe,
    required List<ChartDrawing> drawings,
  }) async {
    try {
      await _api.put('/workspace/drawings', body: {
        'symbol': symbol,
        'timeframe': timeframe,
        'drawings': [
          for (final d in drawings) {'kind': d.toJson()['type'], 'points_json': d.toJson()},
        ],
      });
    } catch (_) {
      // best-effort: drawings stay in memory and will be re-synced next time
    }
  }

  @visibleForTesting
  void handleMarketCandle(Map<String, dynamic> event) => _onCandle(event);

  void _onCandle(Map<String, dynamic> event) {
    final data = event['data'];
    if (data is! Map<String, dynamic>) return;
    if (data['symbol'] != _symbol || data['tf'] != _timeframe.api) return;
    final candle = ChartCandle.fromEvent(data);
    final updated = <ChartCandle>[..._candles];
    if (updated.isEmpty) {
      updated.add(candle);
    } else if (updated.last.ts == candle.ts) {
      updated[updated.length - 1] = candle;
    } else {
      updated.add(candle);
      if (updated.length > 1500) {
        updated.removeRange(0, updated.length - 1500);
      }
    }
    _candles = updated;
    notifyListeners();
  }

  void _onStatusChanged(ConnectionStatus status) {
    if (status == ConnectionStatus.connected) {
      _subscribeCandleChannel();
    }
    notifyListeners();
  }
}

/// A set of charts that share viewport + crosshair.
///
/// When one member pans/zooms/resets it broadcasts the new viewport to the
/// others; crosshair moves are shared too. The origin chart does not receive
/// its own broadcast back (that would be a no-op loop anyway, since the
/// applied viewport is identical).
class ChartSyncGroup {
  final Set<ChartStore> _members = <ChartStore>{};

  bool get isEmpty => _members.isEmpty;

  void join(ChartStore store) => _members.add(store);

  void leave(ChartStore store) => _members.remove(store);

  void onViewportChanged(ChartStore origin) {
    for (final member in _members) {
      if (member == origin) continue;
      member.applySyncedViewport(origin.syncRight, origin.barsVisible);
    }
  }

  void onCrosshairChanged(ChartStore origin) {
    for (final member in _members) {
      if (member == origin) continue;
      member.applySyncedCrosshair(origin.crosshairIndex, origin.crosshairPrice);
    }
  }
}
