import 'package:entryx/features/chart/chart_models.dart';
import 'package:entryx/features/chart/indicator_engine.dart';
import 'package:flutter_test/flutter_test.dart';

ChartCandle candle(double o, double h, double l, double c, double v) => ChartCandle(
      ts: DateTime.fromMillisecondsSinceEpoch(0),
      o: o,
      h: h,
      low: l,
      c: c,
      v: v,
    );

void expectSeries(List<double?> series, List<double?> expected) {
  expect(series.length, expected.length, reason: 'length mismatch');
  for (var i = 0; i < series.length; i++) {
    if (expected[i] == null) {
      expect(series[i], isNull, reason: 'index $i should be warmup');
    } else {
      expect(series[i], closeTo(expected[i]!, 1e-6), reason: 'index $i');
    }
  }
}

void main() {
  group('moving averages', () {
    test('sma basic', () {
      expectSeries(sma([1.0, 2.0, 3.0, 4.0, 5.0], 3), [null, null, 2, 3, 4]);
    });

    test('sma rejects non-positive period', () {
      expect(() => sma([1.0, 2.0], 0), throwsArgumentError);
    });

    test('ema seeds with sma of first window', () {
      // alpha = 2/4 = 0.5; seed at index 2 = mean(1,2,3) = 2
      expectSeries(ema([1.0, 2.0, 3.0, 4.0, 5.0], 3), [null, null, 2, 3, 4]);
    });

    test('wma hand computed', () {
      // period 3, divisor 6: idx2=(1+4+9)/6=14/6, idx3=(2+6+12)/6=20/6, idx4=(3+8+15)/6=26/6
      expectSeries(wma([1.0, 2.0, 3.0, 4.0, 5.0], 3), [null, null, 14 / 6, 20 / 6, 26 / 6]);
    });
  });

  group('oscillators', () {
    test('rsi constant series is 100', () {
      final candles = List.generate(15, (_) => candle(10, 10, 10, 10, 100));
      final out = rsi(candles);
      expect(out.first, isNull);
      expect(out.last, closeTo(100.0, 1e-6));
    });

    test('rsi up-only series is 100', () {
      final candles = [
        for (var i = 1; i < 20; i++)
          candle(i.toDouble(), i.toDouble(), i.toDouble(), i.toDouble(), 1)
      ];
      expect(rsi(candles).last, closeTo(100.0, 1e-6));
    });

    test('macd histogram is macd minus signal', () {
      final candles = [for (var i = 0; i < 60; i++) candle(i.toDouble(), i + 1.0, i - 1.0, i.toDouble(), 1)];
      final out = macd(candles);
      expect(out.macd.length, 60);
      expect(out.macd.first, isNull);
      expect(out.macd.last, isNotNull);
      for (var i = 0; i < 60; i++) {
        final m = out.macd[i];
        final s = out.signal[i];
        if (m != null && s != null) {
          expect(out.histogram[i], closeTo(m - s, 1e-6));
        }
      }
    });

    test('macd rejects fast >= slow', () {
      final candles = [for (var i = 0; i < 30; i++) candle(1, 2, 0.5, 1.5, 1)];
      expect(() => macd(candles, fast: 26, slow: 12), throwsArgumentError);
    });
  });

  group('volume / bands', () {
    test('vwap hand computed', () {
      final candles = [candle(10, 12, 8, 10, 10), candle(11, 13, 9, 11, 10)];
      final out = vwap(candles);
      expect(out[0], closeTo(10.0, 1e-6));
      expect(out[1], closeTo(10.5, 1e-6));
    });

    test('bollinger constant series collapses to the mean', () {
      final candles = List.generate(25, (_) => candle(10, 10, 10, 10, 1));
      final out = bollinger(candles);
      expect(out.mid.last, closeTo(10.0, 1e-6));
      expect(out.upper.last, closeTo(10.0, 1e-6));
      expect(out.lower.last, closeTo(10.0, 1e-6));
    });
  });
}
