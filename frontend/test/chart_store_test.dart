import 'package:entryx/core/api_client.dart';
import 'package:entryx/core/ws_client.dart';
import 'package:entryx/features/chart/chart_models.dart';
import 'package:entryx/features/chart/chart_store.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> candleJson(int ts, {double o = 100, double h = 102, double l = 99, double c = 101, double v = 10}) =>
    {
      'symbol': 'XAUUSD',
      'timeframe': 'H1',
      'ts': DateTime.fromMillisecondsSinceEpoch(ts * 3600000).toIso8601String(),
      'o': o,
      'h': h,
      'l': l,
      'c': c,
      'v': v,
    };

class _FakeApi extends ApiClient {
  @override
  Future<dynamic> get(String path, {bool auth = true}) async {
    if (path.startsWith('/market/candles')) {
      final symbol = Uri.parse(path).queryParameters['symbol'];
      final tf = Uri.parse(path).queryParameters['tf'];
      if (symbol == 'EURUSD' || tf == 'M15') return [];
      return [for (var i = 0; i < 200; i++) candleJson(i)];
    }
    return null;
  }
}

void main() {
  late ChartStore store;

  setUp(() {
    store = ChartStore(api: _FakeApi(), ws: WsClient());
  });

  tearDown(() => store.dispose());

  test('loads candles from the API', () async {
    await Future<void>.delayed(Duration.zero);
    expect(store.hasData, isTrue);
    expect(store.candles, hasLength(200));
    expect(store.candles.first.c, 101);
    expect(store.loading, isFalse);
  });

  test('viewport follows latest and pans within bounds', () async {
    await Future<void>.delayed(Duration.zero);
    expect(store.followingLatest, isTrue);
    expect(store.visibleEnd, 200);

    store.panBy(40);
    expect(store.followingLatest, isFalse);
    expect(store.visibleEnd, 160);

    // panning past the newest bar snaps back to follow mode
    store.panBy(-200);
    expect(store.followingLatest, isTrue);

    // panning far left clamps at the oldest bar
    store.panBy(1000);
    expect(store.visibleStart, 0);
  });

  test('zoom is clamped to the min/max bar count', () async {
    await Future<void>.delayed(Duration.zero);
    store.zoomBy(1000);
    expect(store.barsVisible, ChartStore.minBars);
    store.zoomBy(0.001);
    expect(store.barsVisible, ChartStore.maxBars);
  });

  test('setTimeframe reloads with the new timeframe', () async {
    await Future<void>.delayed(Duration.zero);
    await store.setTimeframe(Timeframe.m15);
    expect(store.timeframe, Timeframe.m15);
    expect(store.hasData, isFalse); // _FakeApi returns [] for M15
  });

  test('setSymbol reloads with the new symbol', () async {
    await Future<void>.delayed(Duration.zero);
    await store.setSymbol('EURUSD');
    expect(store.symbol, 'EURUSD');
    expect(store.hasData, isFalse);
  });

  test('indicator toggles', () async {
    await Future<void>.delayed(Duration.zero);
    expect(store.indicatorEnabled('sma20'), isTrue);
    store.toggleIndicator('sma20');
    expect(store.indicatorEnabled('sma20'), isFalse);
  });

  test('buildIndicators only includes enabled indicators', () async {
    await Future<void>.delayed(Duration.zero);
    final pack = store.buildIndicators();
    final labels = pack.overlays.map((o) => o.label).toList();
    expect(labels, containsAll(['SMA 20', 'SMA 50']));
    expect(labels, isNot(contains('VWAP')));
    expect(pack.bands, isEmpty);

    store.toggleIndicator('vwap');
    store.toggleIndicator('bollinger');
    final pack2 = store.buildIndicators();
    expect(pack2.overlays.map((o) => o.label), contains('VWAP'));
    expect(pack2.bands, hasLength(1));
  });

  test('live candle event updates the forming bar', () async {
    await Future<void>.delayed(Duration.zero);
    final before = store.candles.length;

    // same ts as the last bar -> replaced in place
    store.handleMarketCandle({
      'type': 'market.candle',
      'data': {
        'symbol': 'XAUUSD',
        'tf': 'H1',
        'ts': store.candles.last.ts.toIso8601String(),
        'o': 100,
        'h': 105,
        'l': 98,
        'c': 103,
        'v': 20,
      },
    });
    expect(store.candles.length, before);
    expect(store.candles.last.c, 103);

    // new ts -> appended
    store.handleMarketCandle({
      'type': 'market.candle',
      'data': {
        'symbol': 'XAUUSD',
        'tf': 'H1',
        'ts': DateTime.fromMillisecondsSinceEpoch(
                store.candles.last.ts.millisecondsSinceEpoch + 3600000)
            .toIso8601String(),
        'o': 100,
        'h': 104,
        'l': 99,
        'c': 102,
        'v': 15,
      },
    });
    expect(store.candles.length, before + 1);
  });

  test('live candle event for another symbol is ignored', () async {
    await Future<void>.delayed(Duration.zero);
    final before = store.candles.length;
    store.handleMarketCandle({
      'type': 'market.candle',
      'data': {
        'symbol': 'EURUSD',
        'tf': 'H1',
        'ts': DateTime.fromMillisecondsSinceEpoch(0).toIso8601String(),
        'o': 1,
        'h': 2,
        'l': 0.5,
        'c': 1.5,
        'v': 5,
      },
    });
    expect(store.candles.length, before);
  });

  test('crosshair tracking', () async {
    await Future<void>.delayed(Duration.zero);
    expect(store.crosshairIndex, isNull);
    store.setCrosshair(5, 101.5);
    expect(store.crosshairIndex, 5);
    expect(store.crosshairPrice, closeTo(101.5, 1e-6));
    expect(store.activeBarIndex, 5);
  });
}
