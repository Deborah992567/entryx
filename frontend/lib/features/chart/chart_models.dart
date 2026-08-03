/// Chart domain models: timeframes, candles, overlays, and persistent drawings.
library;

import 'dart:ui';

import 'chart_geometry.dart';

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

/// Active drawing tool in the chart panel.
enum DrawingTool {
  select('Select'),
  trendLine('Trend line'),
  ray('Ray'),
  horizontal('Horizontal line'),
  vertical('Vertical line'),
  rectangle('Rectangle'),
  fibonacci('Fibonacci retracement');

  const DrawingTool(this.label);

  final String label;
}

/// A point in chart space (fractional bar index + price), stable across zoom/pan.
class ChartPoint {
  const ChartPoint(this.bar, this.price);

  final double bar;
  final double price;

  ChartPoint translate(double dBars, double dPrice) =>
      ChartPoint(bar + dBars, price + dPrice);

  Map<String, dynamic> toJson() => {'bar': bar, 'price': price};

  factory ChartPoint.fromJson(Map<String, dynamic> json) => ChartPoint(
        (json['bar'] as num).toDouble(),
        (json['price'] as num).toDouble(),
      );
}

/// A persistent drawing anchored in bar/price space.
sealed class ChartDrawing {
  const ChartDrawing({required this.id, this.color = const Color(0xFF3B9EFF)});

  final int id;
  final Color color;

  Map<String, dynamic> toJson();

  /// Returns a copy shifted by the given bar/price deltas (used when moving).
  ChartDrawing translate(double dBars, double dPrice);

  /// True when the pixel point is within [tolerance] px of the drawing.
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6});
}

class TrendLineDrawing extends ChartDrawing {
  const TrendLineDrawing({required super.id, required this.p1, required this.p2, super.color});

  final ChartPoint p1;
  final ChartPoint p2;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'trendLine',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
      };

  factory TrendLineDrawing.fromJson(Map<String, dynamic> json) => TrendLineDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
      );

  @override
  TrendLineDrawing translate(double dBars, double dPrice) => TrendLineDrawing(
        id: id,
        color: color,
        p1: p1.translate(dBars, dPrice),
        p2: p2.translate(dBars, dPrice),
      );

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
    final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
    return distanceToSegment(point, a, b) <= tolerance;
  }
}

class RayDrawing extends ChartDrawing {
  const RayDrawing({required super.id, required this.p1, required this.p2, super.color});

  final ChartPoint p1;
  final ChartPoint p2;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'ray',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
      };

  factory RayDrawing.fromJson(Map<String, dynamic> json) => RayDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
      );

  @override
  RayDrawing translate(double dBars, double dPrice) => RayDrawing(
        id: id,
        color: color,
        p1: p1.translate(dBars, dPrice),
        p2: p2.translate(dBars, dPrice),
      );

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
    final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
    return distanceToRay(point, a, b) <= tolerance;
  }
}

class HorizontalLineDrawing extends ChartDrawing {
  const HorizontalLineDrawing({required super.id, required this.price, super.color});

  final double price;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'horizontal',
        'id': id,
        'color': color.toARGB32(),
        'price': price,
      };

  factory HorizontalLineDrawing.fromJson(Map<String, dynamic> json) => HorizontalLineDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        price: (json['price'] as num).toDouble(),
      );

  @override
  HorizontalLineDrawing translate(double dBars, double dPrice) =>
      HorizontalLineDrawing(id: id, color: color, price: price + dPrice);

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    return (point.dy - geo.yForPrice(price)).abs() <= tolerance;
  }
}

class VerticalLineDrawing extends ChartDrawing {
  const VerticalLineDrawing({required super.id, required this.bar, super.color});

  final double bar;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'vertical',
        'id': id,
        'color': color.toARGB32(),
        'bar': bar,
      };

  factory VerticalLineDrawing.fromJson(Map<String, dynamic> json) => VerticalLineDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        bar: (json['bar'] as num).toDouble(),
      );

  @override
  VerticalLineDrawing translate(double dBars, double dPrice) =>
      VerticalLineDrawing(id: id, color: color, bar: bar + dBars);

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    return (point.dx - geo.xForBar(bar)).abs() <= tolerance;
  }
}

class RectangleDrawing extends ChartDrawing {
  const RectangleDrawing({required super.id, required this.p1, required this.p2, super.color});

  final ChartPoint p1;
  final ChartPoint p2;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'rectangle',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
      };

  factory RectangleDrawing.fromJson(Map<String, dynamic> json) => RectangleDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
      );

  @override
  RectangleDrawing translate(double dBars, double dPrice) => RectangleDrawing(
        id: id,
        color: color,
        p1: p1.translate(dBars, dPrice),
        p2: p2.translate(dBars, dPrice),
      );

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
    final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
    final left = a.dx < b.dx ? a.dx : b.dx;
    final right = a.dx < b.dx ? b.dx : a.dx;
    final top = a.dy < b.dy ? a.dy : b.dy;
    final bottom = a.dy < b.dy ? b.dy : a.dy;
    if (point.dx >= left && point.dx <= right && point.dy >= top && point.dy <= bottom) {
      return true;
    }
    if (distanceToSegment(point, a, Offset(b.dx, a.dy)) <= tolerance) return true; // top
    if (distanceToSegment(point, Offset(b.dx, a.dy), b) <= tolerance) return true; // right
    if (distanceToSegment(point, b, Offset(a.dx, b.dy)) <= tolerance) return true; // bottom
    if (distanceToSegment(point, Offset(a.dx, b.dy), a) <= tolerance) return true; // left
    return false;
  }
}

class FibRetracementDrawing extends ChartDrawing {
  const FibRetracementDrawing({required super.id, required this.p1, required this.p2, super.color});

  /// Two anchors; the higher price is treated as 0%, the lower as 100%.
  final ChartPoint p1;
  final ChartPoint p2;

  static const List<double> levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];

  ChartPoint get high => p1.price >= p2.price ? p1 : p2;
  ChartPoint get low => p1.price < p2.price ? p1 : p2;

  double levelPrice(double fraction) => high.price - (high.price - low.price) * fraction;

  double get _leftBar => high.bar < low.bar ? high.bar : low.bar;
  double get _rightBar => high.bar < low.bar ? low.bar : high.bar;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'fibonacci',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
      };

  factory FibRetracementDrawing.fromJson(Map<String, dynamic> json) => FibRetracementDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
      );

  @override
  FibRetracementDrawing translate(double dBars, double dPrice) => FibRetracementDrawing(
        id: id,
        color: color,
        p1: p1.translate(dBars, dPrice),
        p2: p2.translate(dBars, dPrice),
      );

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    final left = Offset(geo.xForBar(_leftBar), 0);
    final right = Offset(geo.xForBar(_rightBar), 0);
    for (final f in levels) {
      final y = geo.yForPrice(levelPrice(f));
      final a = Offset(left.dx, y);
      final b = Offset(right.dx, y);
      if (distanceToSegment(point, a, b) <= tolerance) return true;
    }
    return false;
  }
}

/// Parses a drawing from its JSON form (discriminated by `type`).
ChartDrawing chartDrawingFromJson(Map<String, dynamic> json) => switch (json['type']) {
      'trendLine' => TrendLineDrawing.fromJson(json),
      'ray' => RayDrawing.fromJson(json),
      'horizontal' => HorizontalLineDrawing.fromJson(json),
      'vertical' => VerticalLineDrawing.fromJson(json),
      'rectangle' => RectangleDrawing.fromJson(json),
      'fibonacci' => FibRetracementDrawing.fromJson(json),
      _ => throw FormatException('unknown drawing type: ${json['type']}'),
    };
