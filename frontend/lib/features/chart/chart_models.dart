/// Chart domain models: timeframes, candles, and computed overlay series.
library;

import 'dart:ui';

/// Chart timeframes. The API value must match the backend `tf` query pattern.
enum Timeframe {
  m1('M1'),
  m5('M5'),
  m15('M15'),
  m30('M30'),
  h1('H1'),
  h4('H4'),
  d1('D1'),
  w1('W1'),
  mn1('MN1');

  const Timeframe(this.api);

  final String api;

  bool get isIntraday => this != d1 && this != w1 && this != mn1;
}

/// A single candlestick bar.
class ChartCandle {
  const ChartCandle({
    required this.ts,
    required this.o,
    required this.h,
    required this.low,
    required this.c,
    required this.v,
  });

  final DateTime ts;
  final double o;
  final double h;
  final double low;
  final double c;
  final double v;

  bool get isBullish => c >= o;

  /// Parses a REST `CandleOut` payload (`l` key, not `low`).
  factory ChartCandle.fromJson(Map<String, dynamic> json) => ChartCandle(
        ts: DateTime.parse(json['ts'] as String).toLocal(),
        o: (json['o'] as num).toDouble(),
        h: (json['h'] as num).toDouble(),
        low: (json['l'] as num).toDouble(),
        c: (json['c'] as num).toDouble(),
        v: (json['v'] as num).toDouble(),
      );

  /// Parses a `market.candle` WS event payload (uses `tf`, `l`, etc.).
  factory ChartCandle.fromEvent(Map<String, dynamic> data) => ChartCandle(
        ts: DateTime.parse(data['ts'] as String).toLocal(),
        o: (data['o'] as num).toDouble(),
        h: (data['h'] as num).toDouble(),
        low: (data['l'] as num).toDouble(),
        c: (data['c'] as num).toDouble(),
        v: (data['v'] as num).toDouble(),
      );
}

/// A named indicator line aligned to the candle series (leading nulls = warmup).
class Overlay {
  const Overlay({required this.label, required this.series});

  final String label;
  final List<double?> series;
}

/// An envelope indicator (Bollinger-style) rendered as a shaded region.
class Bands {
  const Bands({required this.label, required this.mid, required this.upper, required this.lower});

  final String label;
  final List<double?> mid;
  final List<double?> upper;
  final List<double?> lower;
}

/// Overlay color assignment keyed by indicator label.
const Map<String, Color> overlayColors = {
  'SMA 20': Color(0xFFE8C15A),
  'SMA 50': Color(0xFFE67E22),
  'EMA 20': Color(0xFFF062C0),
  'VWAP': Color(0xFF9B59B6),
  'BB 20,2': Color(0xFF3B9EFF),
};
