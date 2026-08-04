/// Chart domain models: timeframes, candles, overlays, and persistent drawings.
library;

import 'dart:math' as math;
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
  fibonacci('Fibonacci retracement'),
  arrow('Arrow'),
  channel('Channel'),
  ellipse('Ellipse'),
  text('Text label'),
  fibFan('Fibonacci fan'),
  fibExtension('Fibonacci extension'),
  pitchfork('Pitchfork'),
  sr('S/R zone');

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

class ArrowDrawing extends ChartDrawing {
  const ArrowDrawing({required super.id, required this.p1, required this.p2, super.color});

  /// Tail of the arrow; the head points toward [p2].
  final ChartPoint p1;
  final ChartPoint p2;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'arrow',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
      };

  factory ArrowDrawing.fromJson(Map<String, dynamic> json) => ArrowDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
      );

  @override
  ArrowDrawing translate(double dBars, double dPrice) => ArrowDrawing(
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
    if (distanceToSegment(point, a, b) <= tolerance) return true;
    final dir = b - a;
    final len = dir.distance;
    if (len < 1) return false;
    final u = dir / len;
    const arrowLen = 11.0;
    const spread = 0.42;
    final cos = math.cos(spread);
    final sin = math.sin(spread);
    final w1 = b - Offset(u.dx * cos - u.dy * sin, u.dx * sin + u.dy * cos) * arrowLen;
    final w2 = b - Offset(u.dx * cos + u.dy * sin, -u.dx * sin + u.dy * cos) * arrowLen;
    return distanceToSegment(point, b, w1) <= tolerance ||
        distanceToSegment(point, b, w2) <= tolerance;
  }
}

class ChannelDrawing extends ChartDrawing {
  const ChannelDrawing({
    required super.id,
    required this.p1,
    required this.p2,
    required this.p3,
    super.color,
  });

  /// The guide line passes through [p1] and [p2]; the second edge passes
  /// through [p3] parallel to the guide.
  final ChartPoint p1;
  final ChartPoint p2;
  final ChartPoint p3;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'channel',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
        'p3': p3.toJson(),
      };

  factory ChannelDrawing.fromJson(Map<String, dynamic> json) => ChannelDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
        p3: ChartPoint.fromJson(json['p3'] as Map<String, dynamic>),
      );

  @override
  ChannelDrawing translate(double dBars, double dPrice) => ChannelDrawing(
        id: id,
        color: color,
        p1: p1.translate(dBars, dPrice),
        p2: p2.translate(dBars, dPrice),
        p3: p3.translate(dBars, dPrice),
      );

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
    final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
    final c = Offset(geo.xForBar(p3.bar), geo.yForPrice(p3.price));
    final v = b - a;
    if (v.distance < 1) return (point - a).distance <= tolerance;
    return distanceToLine(point, a, v) <= tolerance ||
        distanceToLine(point, c, v) <= tolerance;
  }
}

class EllipseDrawing extends ChartDrawing {
  const EllipseDrawing({required super.id, required this.p1, required this.p2, super.color});

  /// The ellipse is inscribed in the box defined by [p1] and [p2].
  final ChartPoint p1;
  final ChartPoint p2;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'ellipse',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
      };

  factory EllipseDrawing.fromJson(Map<String, dynamic> json) => EllipseDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
      );

  @override
  EllipseDrawing translate(double dBars, double dPrice) => EllipseDrawing(
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
    final rx = (a.dx - b.dx).abs() / 2 + tolerance;
    final ry = (a.dy - b.dy).abs() / 2 + tolerance;
    if (rx <= tolerance || ry <= tolerance) {
      return Rect.fromPoints(a, b).inflate(tolerance).contains(point);
    }
    final cx = (a.dx + b.dx) / 2;
    final cy = (a.dy + b.dy) / 2;
    final dx = (point.dx - cx) / rx;
    final dy = (point.dy - cy) / ry;
    return dx * dx + dy * dy <= 1;
  }
}

class TextDrawing extends ChartDrawing {
  const TextDrawing({required super.id, required this.p1, required this.text, super.color});

  /// Anchor point (top-left of the label in bar/price space).
  final ChartPoint p1;
  final String text;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'text',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'text': text,
      };

  factory TextDrawing.fromJson(Map<String, dynamic> json) => TextDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        text: json['text'] as String? ?? '',
      );

  @override
  TextDrawing translate(double dBars, double dPrice) => TextDrawing(
        id: id,
        color: color,
        p1: p1.translate(dBars, dPrice),
        text: text,
      );

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    final origin = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
    final rect = Rect.fromLTWH(origin.dx, origin.dy - 13, text.length * 6.5 + 8, 16);
    return rect.inflate(tolerance).contains(point);
  }
}

class FibFanDrawing extends ChartDrawing {
  const FibFanDrawing({required super.id, required this.p1, required this.p2, super.color});

  /// Fan lines radiate from [p1] through projected points of the move [p1]→[p2].
  final ChartPoint p1;
  final ChartPoint p2;

  static const List<double> levels = [0.236, 0.382, 0.5, 0.618, 0.786];

  double levelPrice(double fraction) => p1.price - (p1.price - p2.price) * fraction;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'fibfan',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
      };

  factory FibFanDrawing.fromJson(Map<String, dynamic> json) => FibFanDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
      );

  @override
  FibFanDrawing translate(double dBars, double dPrice) => FibFanDrawing(
        id: id,
        color: color,
        p1: p1.translate(dBars, dPrice),
        p2: p2.translate(dBars, dPrice),
      );

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    final origin = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
    for (final f in levels) {
      final through = Offset(geo.xForBar(p2.bar), geo.yForPrice(levelPrice(f)));
      if (distanceToRay(point, origin, through) <= tolerance) return true;
    }
    return false;
  }
}

class FibExtensionDrawing extends ChartDrawing {
  const FibExtensionDrawing({required super.id, required this.p1, required this.p2, super.color});

  /// Extension targets projected beyond the [p1]→[p2] move.
  final ChartPoint p1;
  final ChartPoint p2;

  static const List<double> levels = [0.618, 1.0, 1.272, 1.618, 2.618];

  double levelPrice(double fraction) => p1.price + (p2.price - p1.price) * fraction;

  double get _leftBar => p1.bar < p2.bar ? p1.bar : p2.bar;
  double get _rightBar => p1.bar < p2.bar ? p2.bar : p1.bar;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'fibext',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
      };

  factory FibExtensionDrawing.fromJson(Map<String, dynamic> json) => FibExtensionDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
      );

  @override
  FibExtensionDrawing translate(double dBars, double dPrice) => FibExtensionDrawing(
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
      final a = Offset(left.dx, geo.yForPrice(levelPrice(f)));
      final b = Offset(right.dx, geo.yForPrice(levelPrice(f)));
      if (distanceToSegment(point, a, b) <= tolerance) return true;
    }
    return false;
  }
}

class PitchforkDrawing extends ChartDrawing {
  const PitchforkDrawing({
    required super.id,
    required this.p1,
    required this.p2,
    required this.p3,
    super.color,
  });

  /// The median line runs from [p1] through the midpoint of [p2] and [p3]; the
  /// two prongs are parallels through [p2] and [p3].
  final ChartPoint p1;
  final ChartPoint p2;
  final ChartPoint p3;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'pitchfork',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
        'p3': p3.toJson(),
      };

  factory PitchforkDrawing.fromJson(Map<String, dynamic> json) => PitchforkDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
        p3: ChartPoint.fromJson(json['p3'] as Map<String, dynamic>),
      );

  @override
  PitchforkDrawing translate(double dBars, double dPrice) => PitchforkDrawing(
        id: id,
        color: color,
        p1: p1.translate(dBars, dPrice),
        p2: p2.translate(dBars, dPrice),
        p3: p3.translate(dBars, dPrice),
      );

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
    final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
    final c = Offset(geo.xForBar(p3.bar), geo.yForPrice(p3.price));
    final v = (b + c) / 2 - a;
    if (v.distance < 1) return false;
    return distanceToLine(point, a, v) <= tolerance ||
        distanceToLine(point, b, v) <= tolerance ||
        distanceToLine(point, c, v) <= tolerance;
  }
}

class SRZoneDrawing extends ChartDrawing {
  const SRZoneDrawing({required super.id, required this.p1, required this.p2, super.color});

  /// The zone spans the full chart width between the two anchor prices.
  final ChartPoint p1;
  final ChartPoint p2;

  double get top => p1.price >= p2.price ? p1.price : p2.price;
  double get bottom => p1.price < p2.price ? p1.price : p2.price;

  @override
  Map<String, dynamic> toJson() => {
        'type': 'sr',
        'id': id,
        'color': color.toARGB32(),
        'p1': p1.toJson(),
        'p2': p2.toJson(),
      };

  factory SRZoneDrawing.fromJson(Map<String, dynamic> json) => SRZoneDrawing(
        id: json['id'] as int,
        color: Color(json['color'] as int? ?? 0xFF3B9EFF),
        p1: ChartPoint.fromJson(json['p1'] as Map<String, dynamic>),
        p2: ChartPoint.fromJson(json['p2'] as Map<String, dynamic>),
      );

  @override
  SRZoneDrawing translate(double dBars, double dPrice) => SRZoneDrawing(
        id: id,
        color: color,
        p1: p1.translate(dBars, dPrice),
        p2: p2.translate(dBars, dPrice),
      );

  @override
  bool hitTest(Offset point, ChartGeometry geo, {double tolerance = 6}) {
    if (!geo.hasData) return false;
    final yTop = geo.yForPrice(top);
    final yBottom = geo.yForPrice(bottom);
    final inX = point.dx >= -tolerance && point.dx <= geo.chartWidth + tolerance;
    if (!inX) return false;
    if (point.dy >= yTop - tolerance && point.dy <= yBottom + tolerance) return true;
    return (point.dy - yTop).abs() <= tolerance || (point.dy - yBottom).abs() <= tolerance;
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
      'arrow' => ArrowDrawing.fromJson(json),
      'channel' => ChannelDrawing.fromJson(json),
      'ellipse' => EllipseDrawing.fromJson(json),
      'text' => TextDrawing.fromJson(json),
      'fibfan' => FibFanDrawing.fromJson(json),
      'fibext' => FibExtensionDrawing.fromJson(json),
      'pitchfork' => PitchforkDrawing.fromJson(json),
      'sr' => SRZoneDrawing.fromJson(json),
      'fibonacci' => FibRetracementDrawing.fromJson(json),
      _ => throw FormatException('unknown drawing type: ${json['type']}'),
    };
