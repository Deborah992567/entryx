/// Shared chart geometry: converts between bar/price space and pixels, and
/// holds the layout constants so the painter and the panel stay in sync.
library;

import 'dart:math' as math;

import 'package:flutter/widgets.dart';

import 'chart_models.dart';

class ChartGeometry {
  ChartGeometry({
    required this.size,
    required this.candles,
    required this.start,
    required this.end,
    this.overlays = const [],
    this.bands = const [],
    this.lastPrice,
  }) {
    _computeRange();
  }

  final Size size;
  final List<ChartCandle> candles;
  final int start;
  final int end;
  final List<Overlay> overlays;
  final List<Bands> bands;
  final double? lastPrice;

  static const double priceWidth = 58;
  static const double timeHeight = 20;
  static const double volumeRatio = 0.22;
  static const double pricePadding = 0.06;

  late double minPrice;
  late double maxPrice;

  double get chartWidth => size.width - priceWidth;
  double get chartHeight => size.height - timeHeight;
  double get priceBottom => chartHeight * (1 - volumeRatio);
  double get volumeTop => priceBottom;
  int get visibleCount => end - start;
  double get barWidth => visibleCount > 0 ? chartWidth / visibleCount : 1.0;

  Rect get priceRect => Rect.fromLTRB(0, 0, chartWidth, priceBottom);

  bool get hasData => candles.isNotEmpty && start < end && minPrice.isFinite;

  void _computeRange() {
    var minP = double.infinity;
    var maxP = double.negativeInfinity;
    for (var i = start; i < end && i < candles.length; i++) {
      final c = candles[i];
      if (c.low < minP) minP = c.low;
      if (c.h > maxP) maxP = c.h;
    }
    for (final o in overlays) {
      _extendRange(o.series, minP, maxP, (v) => minP = v, (v) => maxP = v);
    }
    for (final b in bands) {
      for (final s in [b.mid, b.upper, b.lower]) {
        _extendRange(s, minP, maxP, (v) => minP = v, (v) => maxP = v);
      }
    }
    final last = lastPrice;
    if (last != null) {
      if (last < minP) minP = last;
      if (last > maxP) maxP = last;
    }
    if (!minP.isFinite) {
      minPrice = 0;
      maxPrice = 1;
      return;
    }
    final pad = (maxP - minP) * pricePadding;
    minP -= pad;
    maxP += pad;
    if (maxP <= minP) maxP = minP + 1;
    minPrice = minP;
    maxPrice = maxP;
  }

  void _extendRange(
    List<double?> series,
    double minP,
    double maxP,
    void Function(double) takeMin,
    void Function(double) takeMax,
  ) {
    for (var i = start; i < end && i < series.length; i++) {
      final v = series[i];
      if (v != null) {
        if (v < minP) takeMin(v);
        if (v > maxP) takeMax(v);
      }
    }
  }

  double xForBar(double bar) => (bar - start + 0.5) * barWidth;

  double yForPrice(double price) =>
      priceBottom - (price - minPrice) / (maxPrice - minPrice) * priceBottom;

  double barAtX(double x) => start - 0.5 + x / barWidth;

  double priceAtY(double y) => maxPrice - y / priceBottom * (maxPrice - minPrice);

  /// A "nice" grid step for the given number of divisions.
  double niceStep(double rough) {
    if (rough <= 0) return 1;
    final mag = math.pow(10.0, (math.log(rough) / math.ln10).floor()).toDouble();
    final norm = rough / mag;
    double nice;
    if (norm < 1.5) {
      nice = 1;
    } else if (norm < 3.5) {
      nice = 2;
    } else if (norm < 7.5) {
      nice = 5;
    } else {
      nice = 10;
    }
    return nice * mag;
  }

  int decimalsFor(double step) {
    if (step >= 1) return 0;
    var s = step;
    var d = 0;
    while (s < 1) {
      s *= 10;
      d++;
    }
    return d;
  }
}

double distanceToSegment(Offset p, Offset a, Offset b) {
  final ab = b - a;
  final len2 = ab.dx * ab.dx + ab.dy * ab.dy;
  if (len2 == 0) return (p - a).distance;
  final t = (((p - a).dx * ab.dx + (p - a).dy * ab.dy) / len2).clamp(0.0, 1.0);
  return (p - (a + ab * t)).distance;
}

double distanceToRay(Offset p, Offset a, Offset b) {
  final ab = b - a;
  final len2 = ab.dx * ab.dx + ab.dy * ab.dy;
  if (len2 == 0) return (p - a).distance;
  final t = ((p - a).dx * ab.dx + (p - a).dy * ab.dy) / len2;
  if (t < 0) return (p - a).distance;
  return (p - (a + ab * t)).distance;
}
