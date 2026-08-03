import 'dart:ui' as ui;

import 'package:entryx/core/api_client.dart';
import 'package:entryx/core/ws_client.dart';
import 'package:entryx/features/chart/candle_painter.dart';
import 'package:entryx/features/chart/chart_geometry.dart';
import 'package:entryx/features/chart/chart_models.dart';
import 'package:entryx/features/chart/chart_store.dart';
import 'package:flutter_test/flutter_test.dart';

ChartCandle mk(int i, {double low = 100, double high = 110, double c = 105, double v = 10}) =>
    ChartCandle(
      ts: DateTime.fromMillisecondsSinceEpoch(i * 3600000),
      o: (low + high) / 2,
      h: high,
      low: low,
      c: c,
      v: v,
    );

ChartGeometry geo({int count = 100}) => ChartGeometry(
      size: const ui.Size(1000, 600),
      candles: [for (var i = 0; i < count; i++) mk(i)],
      start: 0,
      end: count,
    );

void main() {
  group('ChartGeometry', () {
    test('converts bar <-> pixel and price <-> pixel', () {
      final g = geo();
      expect(g.chartWidth, closeTo(942, 0.01));
      expect(g.priceBottom, closeTo(452.4, 0.01));
      for (final bar in [0.0, 10.5, 50.0, 99.0]) {
        expect(g.barAtX(g.xForBar(bar)), closeTo(bar, 1e-9));
      }
      for (final price in [99.4, 100.0, 105.5, 110.6]) {
        expect(g.priceAtY(g.yForPrice(price)), closeTo(price, 1e-6));
      }
    });

    test('range includes padding', () {
      final g = geo();
      expect(g.minPrice, closeTo(99.4, 1e-9));
      expect(g.maxPrice, closeTo(110.6, 1e-9));
    });

    test('nice step picks 1/2/5 multiples', () {
      final g = geo();
      expect(g.niceStep(0.0001), closeTo(0.0001, 1e-12));
      expect(g.niceStep(0.3), closeTo(0.2, 1e-12));
      expect(g.niceStep(3.0), closeTo(2.0, 1e-12));
      expect(g.niceStep(4.0), closeTo(5.0, 1e-12));
      expect(g.decimalsFor(0.5), 1);
      expect(g.decimalsFor(0.05), 2);
      expect(g.decimalsFor(5), 0);
    });
  });

  group('drawing serialization', () {
    List<ChartDrawing> all() => [
          TrendLineDrawing(id: 1, p1: const ChartPoint(10, 100), p2: const ChartPoint(90, 110)),
          RayDrawing(id: 2, p1: const ChartPoint(5, 101), p2: const ChartPoint(80, 109)),
          HorizontalLineDrawing(id: 3, price: 105.25),
          VerticalLineDrawing(id: 4, bar: 42),
          RectangleDrawing(id: 5, p1: const ChartPoint(20, 102), p2: const ChartPoint(70, 108)),
          FibRetracementDrawing(id: 6, p1: const ChartPoint(10, 110), p2: const ChartPoint(90, 100)),
        ];

    test('round-trips every drawing type', () {
      for (final d in all()) {
        final restored = chartDrawingFromJson(d.toJson());
        expect(restored.runtimeType, d.runtimeType);
        expect(restored.id, d.id);
        expect(restored.toJson(), d.toJson());
      }
    });

    test('fib levels are ordered high to low', () {
      final fib = FibRetracementDrawing(
          id: 1, p1: const ChartPoint(10, 110), p2: const ChartPoint(90, 100));
      expect(fib.high.price, 110);
      expect(fib.low.price, 100);
      expect(fib.levelPrice(0), closeTo(110, 1e-9));
      expect(fib.levelPrice(1), closeTo(100, 1e-9));
      expect(fib.levelPrice(0.5), closeTo(105, 1e-9));
    });
  });

  group('drawing hit-testing', () {
    test('trendline hits along its segment', () {
      final g = geo();
      final line = TrendLineDrawing(
          id: 1, p1: const ChartPoint(10, 100), p2: const ChartPoint(90, 110));
      // midpoint in pixel space is on the line
      final a = Offset(g.xForBar(10), g.yForPrice(100));
      final b = Offset(g.xForBar(90), g.yForPrice(110));
      final mid = (a + b) / 2;
      expect(line.hitTest(mid, g), isTrue);
      expect(line.hitTest(const Offset(5, 5), g), isFalse);
    });

    test('horizontal line hits on its price level', () {
      final g = geo();
      final line = HorizontalLineDrawing(id: 1, price: 105);
      final p = Offset(300, g.yForPrice(105));
      expect(line.hitTest(p, g), isTrue);
      expect(line.hitTest(Offset(300, g.yForPrice(105) + 100), g), isFalse);
    });

    test('rectangle hits inside and on border, not outside', () {
      final g = geo();
      final rect = RectangleDrawing(
          id: 1, p1: const ChartPoint(30, 103), p2: const ChartPoint(70, 107));
      final center = Offset(g.xForBar(50), g.yForPrice(105));
      final outside = Offset(g.xForBar(80), g.yForPrice(102));
      expect(rect.hitTest(center, g), isTrue);
      expect(rect.hitTest(outside, g), isFalse);
    });

    test('fib hits on any level', () {
      final g = geo();
      final fib = FibRetracementDrawing(
          id: 1, p1: const ChartPoint(10, 110), p2: const ChartPoint(90, 100));
      expect(fib.hitTest(Offset(g.xForBar(50), g.yForPrice(105)), g), isTrue);
      // 103 is midway between levels 0.618 (103.82) and 0.786 (102.14) -> no hit
      expect(fib.hitTest(Offset(g.xForBar(50), g.yForPrice(103)), g), isFalse);
    });
  });

  group('store drawing ops', () {
    late ChartStore store;

    setUp(() {
      store = ChartStore(api: _FakeApi(), ws: WsClient());
    });

    tearDown(() => store.dispose());

    test('add, select, update, remove, clear', () async {
      await Future<void>.delayed(Duration.zero);
      final line = TrendLineDrawing(
          id: store.nextDrawingId, p1: const ChartPoint(10, 100), p2: const ChartPoint(90, 110));
      store.addDrawing(line);
      expect(store.drawings, hasLength(1));
      expect(store.nextDrawingId, line.id + 1);

      store.selectDrawing(line.id);
      expect(store.selectedDrawingId, line.id);

      final moved = line.translate(5, -2);
      store.updateDrawing(moved);
      expect((store.drawings.single as TrendLineDrawing).p1.bar, 15);

      store.removeSelectedDrawing();
      expect(store.drawings, isEmpty);
      expect(store.selectedDrawingId, isNull);
    });

    test('tool switching clears selection', () async {
      await Future<void>.delayed(Duration.zero);
      final line = HorizontalLineDrawing(id: store.nextDrawingId, price: 105);
      store.addDrawing(line);
      store.selectDrawing(line.id);
      store.setTool(DrawingTool.trendLine);
      expect(store.selectedDrawingId, isNull);
      expect(store.tool, DrawingTool.trendLine);
    });

    test('translate keeps the same id', () {
      final line = TrendLineDrawing(
          id: 7, p1: const ChartPoint(10, 100), p2: const ChartPoint(90, 110));
      final moved = line.translate(1, 2);
      expect(moved.id, 7);
      expect(moved.p1.bar, 11);
      expect(moved.p2.price, 112);
    });
  });

  group('painter smoke', () {
    test('renders candles + drawings without throwing', () {
      final g = geo();
      final recorder = ui.PictureRecorder();
      final canvas = ui.Canvas(recorder);
      final painter = CandleChartPainter(
        candles: g.candles,
        start: 0,
        end: g.end,
        timeframe: Timeframe.h1,
        symbol: 'XAUUSD',
        drawings: [
          TrendLineDrawing(id: 1, p1: const ChartPoint(10, 100), p2: const ChartPoint(90, 110)),
          FibRetracementDrawing(id: 2, p1: const ChartPoint(10, 110), p2: const ChartPoint(90, 100)),
        ],
        selectedDrawingId: 1,
        overlays: const [],
        bands: const [],
      );
      painter.paint(canvas, const ui.Size(1000, 600));
      recorder.endRecording();
    });
  });
}

class _FakeApi extends ApiClient {
  @override
  Future<dynamic> get(String path, {bool auth = true}) async {
    if (path.startsWith('/market/candles')) {
      return [
        for (var i = 0; i < 100; i++)
          {
            'symbol': 'XAUUSD',
            'timeframe': 'H1',
            'ts': DateTime.fromMillisecondsSinceEpoch(i * 3600000).toIso8601String(),
            'o': 105,
            'h': 110,
            'l': 100,
            'c': 105,
            'v': 10,
          }
      ];
    }
    return null;
  }
}
