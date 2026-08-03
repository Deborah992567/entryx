/// Client-side indicator engine.
///
/// Pure functions matching the backend math in `app/services/indicators.py` so
/// overlay values are deterministic and identical across server and client.
/// All series are aligned to the candle list (leading nulls = warmup).
library;

import 'dart:math' as math;

import 'chart_models.dart';

double _round(double v, [int digits = 8]) {
  final m = math.pow(10, digits).toDouble();
  return (v * m).roundToDouble() / m;
}

List<double?> sma(List<double> values, int period) {
  if (period <= 0) {
    throw ArgumentError('period must be positive');
  }
  final out = List<double?>.filled(values.length, null);
  var window = 0.0;
  for (var i = 0; i < values.length; i++) {
    window += values[i];
    if (i >= period) window -= values[i - period];
    if (i >= period - 1) out[i] = _round(window / period);
  }
  return out;
}

List<double?> ema(List<double> values, int period) {
  if (period <= 0) {
    throw ArgumentError('period must be positive');
  }
  final out = List<double?>.filled(values.length, null);
  if (values.length < period) return out;
  final alpha = 2.0 / (period + 1.0);
  var seed = 0.0;
  for (var i = 0; i < period; i++) {
    seed += values[i];
  }
  seed /= period;
  out[period - 1] = _round(seed);
  for (var i = period; i < values.length; i++) {
    out[i] = _round(values[i] * alpha + out[i - 1]! * (1 - alpha));
  }
  return out;
}

List<double?> wma(List<double> values, int period) {
  if (period <= 0) {
    throw ArgumentError('period must be positive');
  }
  final out = List<double?>.filled(values.length, null);
  final divisor = period * (period + 1) / 2.0;
  for (var i = period - 1; i < values.length; i++) {
    var total = 0.0;
    for (var j = 0; j < period; j++) {
      total += values[i - j] * (period - j);
    }
    out[i] = _round(total / divisor);
  }
  return out;
}

List<double?> rsi(List<ChartCandle> candles, {int period = 14}) {
  if (period <= 0) {
    throw ArgumentError('period must be positive');
  }
  final out = List<double?>.filled(candles.length, null);
  if (candles.length <= period) return out;
  final gains = <double>[];
  final losses = <double>[];
  for (var i = 1; i < candles.length; i++) {
    final change = candles[i].c - candles[i - 1].c;
    gains.add(change > 0 ? change : 0.0);
    losses.add(change < 0 ? -change : 0.0);
  }
  var avgGain = gains.take(period).reduce((a, b) => a + b) / period;
  var avgLoss = losses.take(period).reduce((a, b) => a + b) / period;
  out[period] = _rsiValue(avgGain, avgLoss);
  for (var i = period + 1; i < candles.length; i++) {
    avgGain = (avgGain * (period - 1) + gains[i - 1]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i - 1]) / period;
    out[i] = _rsiValue(avgGain, avgLoss);
  }
  return out;
}

double _rsiValue(double avgGain, double avgLoss) {
  if (avgLoss == 0) return 100.0;
  final rs = avgGain / avgLoss;
  return _round(100.0 - 100.0 / (1.0 + rs), 4);
}

List<double?> vwap(List<ChartCandle> candles) {
  final out = List<double?>.filled(candles.length, null);
  var cumPv = 0.0;
  var cumV = 0.0;
  for (var i = 0; i < candles.length; i++) {
    final tp = (candles[i].h + candles[i].low + candles[i].c) / 3.0;
    cumPv += tp * candles[i].v;
    cumV += candles[i].v;
    if (cumV > 0) out[i] = _round(cumPv / cumV);
  }
  return out;
}

class MacdResult {
  const MacdResult({required this.macd, required this.signal, required this.histogram});

  final List<double?> macd;
  final List<double?> signal;
  final List<double?> histogram;
}

MacdResult macd(List<ChartCandle> candles, {int fast = 12, int slow = 26, int signal = 9}) {
  if (fast >= slow) {
    throw ArgumentError('fast must be smaller than slow');
  }
  final closes = candles.map((c) => c.c).toList();
  final fastEma = ema(closes, fast);
  final slowEma = ema(closes, slow);
  final macdSeries = List<double?>.filled(candles.length, null);
  for (var i = 0; i < candles.length; i++) {
    if (fastEma[i] != null && slowEma[i] != null) {
      macdSeries[i] = _round(fastEma[i]! - slowEma[i]!);
    }
  }
  final signalSeries = _emaOver(macdSeries, signal);
  final hist = List<double?>.filled(candles.length, null);
  for (var i = 0; i < candles.length; i++) {
    if (macdSeries[i] != null && signalSeries[i] != null) {
      hist[i] = _round(macdSeries[i]! - signalSeries[i]!);
    }
  }
  return MacdResult(macd: macdSeries, signal: signalSeries, histogram: hist);
}

List<double?> _emaOver(List<double?> series, int period) {
  final out = List<double?>.filled(series.length, null);
  final values = <(int, double)>[];
  for (var i = 0; i < series.length; i++) {
    final v = series[i];
    if (v != null) values.add((i, v));
  }
  if (values.length < period) return out;
  final alpha = 2.0 / (period + 1.0);
  var seed = 0.0;
  for (var j = 0; j < period; j++) {
    seed += values[j].$2;
  }
  seed /= period;
  out[values[period - 1].$1] = _round(seed);
  var prev = seed;
  for (var i = period; i < values.length; i++) {
    prev = values[i].$2 * alpha + prev * (1 - alpha);
    out[values[i].$1] = _round(prev);
  }
  return out;
}

class BollingerResult {
  const BollingerResult({required this.mid, required this.upper, required this.lower});

  final List<double?> mid;
  final List<double?> upper;
  final List<double?> lower;
}

BollingerResult bollinger(List<ChartCandle> candles, {int period = 20, double mult = 2.0}) {
  final mid = sma(candles.map((c) => c.c).toList(), period);
  final upper = List<double?>.filled(candles.length, null);
  final lower = List<double?>.filled(candles.length, null);
  for (var i = period - 1; i < candles.length; i++) {
    final base = mid[i];
    if (base == null) continue;
    var sum = 0.0;
    for (var j = i - period + 1; j <= i; j++) {
      sum += math.pow(candles[j].c - base, 2).toDouble();
    }
    final sd = math.sqrt(sum / period);
    upper[i] = _round(base + mult * sd);
    lower[i] = _round(base - mult * sd);
  }
  return BollingerResult(mid: mid, upper: upper, lower: lower);
}

/// Overlays + bands a store produces for a candle set.
class IndicatorPack {
  const IndicatorPack({required this.overlays, required this.bands});

  final List<Overlay> overlays;
  final List<Bands> bands;
}
