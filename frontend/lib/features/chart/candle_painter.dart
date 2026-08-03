/// Canvas chart engine: candlesticks, volume pane, price/time scales, grid,
/// indicator overlays, bands, and a crosshair with OHLC readout.
///
/// Pure rendering: all geometry is derived from the visible window
/// (`start`..`end`) plus explicit crosshair state, so the painter never owns
/// data or gesture state.
library;

import 'dart:math' as math;

import 'package:flutter/widgets.dart';

import 'chart_models.dart' as models;

class CandleChartPainter extends CustomPainter {
  CandleChartPainter({
    required this.candles,
    required this.start,
    required this.end,
    required this.timeframe,
    this.symbol = '',
    this.crosshairIndex,
    this.crosshairPrice,
    this.overlays = const [],
    this.bands = const [],
    this.lastPrice,
    this.connected = true,
  });

  final List<models.ChartCandle> candles;
  final int start;
  final int end;
  final models.Timeframe timeframe;
  final String symbol;
  final int? crosshairIndex;
  final double? crosshairPrice;
  final List<models.Overlay> overlays;
  final List<models.Bands> bands;
  final double? lastPrice;
  final bool connected;

  static const double priceWidth = 58;
  static const double timeHeight = 20;

  @override
  void paint(Canvas canvas, Size size) {
    final chartRect =
        Rect.fromLTRB(0, 0, size.width - priceWidth, size.height - timeHeight);
    if (chartRect.width <= 0 || chartRect.height <= 0 || candles.isEmpty || start >= end) {
      return;
    }

    final volumeRect = Rect.fromLTWH(
      0,
      chartRect.bottom - chartRect.height * 0.22,
      chartRect.width,
      chartRect.height * 0.22,
    );
    final priceRect = Rect.fromLTRB(
      0,
      0,
      chartRect.width,
      volumeRect.top,
    );

    var minP = double.infinity;
    var maxP = double.negativeInfinity;
    for (var i = start; i < end; i++) {
      final c = candles[i];
      if (c.low < minP) minP = c.low;
      if (c.h > maxP) maxP = c.h;
    }
    for (final o in overlays) {
      _extendRange(o.series, start, end, (p) => minP = p < minP ? p : minP, (p) => maxP = p > maxP ? p : maxP);
    }
    for (final b in bands) {
      for (final s in [b.mid, b.upper, b.lower]) {
        _extendRange(s, start, end, (p) => minP = p < minP ? p : minP, (p) => maxP = p > maxP ? p : maxP);
      }
    }
    final last = lastPrice;
    if (last != null) {
      if (last < minP) minP = last;
      if (last > maxP) maxP = last;
    }
    if (!minP.isFinite) return;

    final pad = (maxP - minP) * 0.06;
    minP -= pad;
    maxP += pad;
    if (maxP <= minP) maxP = minP + 1;

    final visibleCount = end - start;
    final barWidth = priceRect.width / visibleCount;
    final bodyWidth = math.max(1.0, math.min(14.0, barWidth * 0.72));

    double yFor(double price) =>
        priceRect.bottom - (price - minP) / (maxP - minP) * priceRect.height;

    _drawGridAndScale(canvas, priceRect, minP, maxP, visibleCount, barWidth, yFor);

    var maxV = 0.0;
    for (var i = start; i < end; i++) {
      if (candles[i].v > maxV) maxV = candles[i].v;
    }
    _drawVolume(canvas, volumeRect, barWidth, bodyWidth, maxV);
    _drawCandles(canvas, priceRect, barWidth, bodyWidth, yFor);
    for (final b in bands) {
      _drawBands(canvas, priceRect, barWidth, b, yFor);
    }
    for (final o in overlays) {
      _drawLine(canvas, priceRect, barWidth, o.series, _colorForOverlay(o.label), yFor);
    }

    if (last != null) {
      _drawLastPriceTag(canvas, priceRect, last, yFor(last));
    }

    if (crosshairIndex != null) {
      _drawCrosshair(canvas, priceRect, barWidth, crosshairIndex!, crosshairPrice, yFor, minP, maxP);
    }

    _drawOhlc(canvas, crosshairIndex ?? end - 1);
  }

  // ----------------------------------------------------------------------- scale

  void _drawGridAndScale(
    Canvas canvas,
    Rect priceRect,
    double minP,
    double maxP,
    int visibleCount,
    double barWidth,
    double Function(double) yFor,
  ) {
    final grid = Paint()
      ..color = const Color(0xFF242B36).withValues(alpha: 0.55)
      ..strokeWidth = 0.5;

    final step = _niceStep((maxP - minP) / 6);
    final decimals = _decimalsFor(step);
    var price = (minP / step).floorToDouble() * step;
    while (price <= maxP) {
      final y = yFor(price);
      canvas.drawLine(Offset(0, y), Offset(priceRect.width, y), grid);
      final label = price.toStringAsFixed(decimals);
      _drawText(canvas, label, Offset(priceRect.width + 6, y - 6),
          const Color(0xFF8B95A5), fontSize: 9.5);
      price += step;
    }

    final barStep = math.max(1, (visibleCount / 6).round());
    for (var i = start; i < end; i += barStep) {
      final x = _xForBar(priceRect, barWidth, i);
      canvas.drawLine(Offset(x, 0), Offset(x, priceRect.height), grid);
      final label = _formatTime(candles[i].ts);
      _drawText(canvas, label, Offset(x - 14, priceRect.bottom + 4),
          const Color(0xFF8B95A5), fontSize: 9.5);
    }
  }

  // --------------------------------------------------------------------- volume

  void _drawVolume(Canvas canvas, Rect rect, double barWidth, double bodyWidth, double maxV) {
    final paint = Paint();
    for (var i = start; i < end; i++) {
      final candle = candles[i];
      final x = _xForBar(rect, barWidth, i);
      final height = maxV <= 0 ? 0.0 : (candle.v / maxV) * rect.height;
      paint.color = (candle.isBullish ? const Color(0xFF2ECC71) : const Color(0xFFE74C3C))
          .withValues(alpha: 0.55);
      canvas.drawRect(
        Rect.fromLTRB(x - bodyWidth / 2, rect.bottom - height, x + bodyWidth / 2, rect.bottom),
        paint,
      );
    }
  }

  // -------------------------------------------------------------------- candles

  void _drawCandles(
    Canvas canvas,
    Rect rect,
    double barWidth,
    double bodyWidth,
    double Function(double) yFor,
  ) {
    final wick = Paint()..strokeWidth = 1;
    final body = Paint();
    for (var i = start; i < end; i++) {
      final candle = candles[i];
      final color = candle.isBullish ? const Color(0xFF2ECC71) : const Color(0xFFE74C3C);
      final x = _xForBar(rect, barWidth, i);
      wick.color = color;
      canvas.drawLine(Offset(x, yFor(candle.h)), Offset(x, yFor(candle.low)), wick);
      final top = yFor(math.max(candle.o, candle.c));
      final bottom = yFor(math.min(candle.o, candle.c));
      body.color = color;
      canvas.drawRect(
        Rect.fromLTRB(x - bodyWidth / 2, top, x + bodyWidth / 2, math.max(bottom, top + 1)),
        body,
      );
    }
  }

  // -------------------------------------------------------------------- overlays

  void _drawBands(Canvas canvas, Rect rect, double barWidth, models.Bands bands, double Function(double) yFor) {
    final fill = Paint()..color = _colorForOverlay(bands.label).withValues(alpha: 0.10);
    final path = Path();
    var started = false;
    for (var i = start; i < end; i++) {
      final u = bands.upper[i];
      final l = bands.lower[i];
      if (u == null || l == null) {
        started = false;
        continue;
      }
      final x = _xForBar(rect, barWidth, i);
      if (!started) {
        path.moveTo(x, yFor(u));
        started = true;
      } else {
        path.lineTo(x, yFor(u));
      }
    }
    final reverse = <Offset>[];
    for (var i = end - 1; i >= start; i--) {
      final u = bands.upper[i];
      final l = bands.lower[i];
      if (u == null || l == null) continue;
      final x = _xForBar(rect, barWidth, i);
      reverse.add(Offset(x, yFor(l)));
    }
    if (started && reverse.isNotEmpty) {
      for (final o in reverse) {
        path.lineTo(o.dx, o.dy);
      }
      path.close();
      canvas.drawPath(path, fill);
    }
    _drawLine(canvas, rect, barWidth, bands.mid, _colorForOverlay(bands.label), yFor);
    _drawLine(canvas, rect, barWidth, bands.upper, _colorForOverlay(bands.label).withValues(alpha: 0.6), yFor);
    _drawLine(canvas, rect, barWidth, bands.lower, _colorForOverlay(bands.label).withValues(alpha: 0.6), yFor);
  }

  void _drawLine(
    Canvas canvas,
    Rect rect,
    double barWidth,
    List<double?> series,
    Color color,
    double Function(double) yFor,
  ) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.1
      ..style = PaintingStyle.stroke;
    final path = Path();
    var started = false;
    for (var i = start; i < end; i++) {
      final value = series[i];
      if (value == null) {
        started = false;
        continue;
      }
      final x = _xForBar(rect, barWidth, i);
      final y = yFor(value);
      if (!started) {
        path.moveTo(x, y);
        started = true;
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, paint);
  }

  // ------------------------------------------------------------------- crosshair

  void _drawCrosshair(
    Canvas canvas,
    Rect rect,
    double barWidth,
    int index,
    double? price,
    double Function(double) yFor,
    double minP,
    double maxP,
  ) {
    final x = _xForBar(rect, barWidth, index);
    final line = Paint()
      ..color = const Color(0xFF8B95A5).withValues(alpha: 0.9)
      ..strokeWidth = 0.8;
    canvas.drawLine(Offset(x, 0), Offset(x, rect.height), line);

    final p = price ?? candles[index].c;
    final y = yFor(p);
    canvas.drawLine(Offset(0, y), Offset(rect.width, y), line);

    // price tag on the right scale
    final tag = Paint()..color = const Color(0xFF3B9EFF);
    final label = p.toStringAsFixed(_decimalsFor((maxP - minP) / 40));
    final tp = TextPainter(
      text: TextSpan(
        text: label,
        style: const TextStyle(color: Color(0xFFFFFFFF), fontSize: 9.5),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final tagRect = Rect.fromLTWH(rect.width + 1, y - 7, 34, 14);
    canvas.drawRect(tagRect, tag);
    tp.paint(canvas, Offset(rect.width + 6, y - 5.5));
  }

  void _drawLastPriceTag(Canvas canvas, Rect rect, double price, double y) {
    final decimals = _decimalsFor(_niceStep((rect.height) / 60));
    final label = price.toStringAsFixed(decimals);
    final tp = TextPainter(
      text: TextSpan(text: label, style: const TextStyle(color: Color(0xFFFFFFFF), fontSize: 9.5)),
      textDirection: TextDirection.ltr,
    )..layout();
    final w = tp.width + 12;
    final paint = Paint()..color = const Color(0xFF3B9EFF);
    canvas.drawRect(Rect.fromLTWH(rect.width + 1, y - 7, w, 14), paint);
    tp.paint(canvas, Offset(rect.width + 7, y - 5.5));
  }

  // --------------------------------------------------------------------- OHLC

  void _drawOhlc(Canvas canvas, int index) {
    if (index < 0 || index >= candles.length) return;
    final c = candles[index];
    final color = c.isBullish ? const Color(0xFF2ECC71) : const Color(0xFFE74C3C);
    final parts = <TextSpan>[
      TextSpan(
        text: symbol.isEmpty ? '' : '$symbol  ',
        style: const TextStyle(color: Color(0xFF8B95A5)),
      ),
      TextSpan(
        text: 'O ${_price(c.o)}  H ${_price(c.h)}  L ${_price(c.low)}  C ${_price(c.c)}  ',
        style: TextStyle(color: color),
      ),
      TextSpan(text: 'V ${_vol(c.v)}', style: const TextStyle(color: Color(0xFF8B95A5))),
    ];
    final tp = TextPainter(
      text: TextSpan(style: const TextStyle(fontSize: 10), children: parts),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, const Offset(6, 6));
  }

  String _price(double v) => v.toStringAsFixed(5);
  String _vol(double v) => v >= 1000 ? '${(v / 1000).toStringAsFixed(1)}k' : v.toStringAsFixed(0);

  // -------------------------------------------------------------------- helpers

  double _xForBar(Rect rect, double barWidth, int index) =>
      rect.left + (index - start) * barWidth + barWidth / 2;

  void _extendRange(
    List<double?> series,
    int start,
    int end,
    void Function(double) takeMin,
    void Function(double) takeMax,
  ) {
    for (var i = start; i < end && i < series.length; i++) {
      final v = series[i];
      if (v != null) {
        takeMin(v);
        takeMax(v);
      }
    }
  }

  String _formatTime(DateTime ts) {
    if (timeframe.isIntraday) {
      return '${_two(ts.hour)}:${_two(ts.minute)}';
    }
    return '${_two(ts.month)}/${_two(ts.day)}';
  }

  String _two(int v) => v.toString().padLeft(2, '0');

  Color _colorForOverlay(String label) => models.overlayColors[label] ?? const Color(0xFF3B9EFF);

  double _niceStep(double rough) {
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

  int _decimalsFor(double step) {
    if (step >= 1) return 0;
    var s = step;
    var d = 0;
    while (s < 1) {
      s *= 10;
      d++;
    }
    return d;
  }

  void _drawText(
    Canvas canvas,
    String text,
    Offset offset,
    Color color, {
    double fontSize = 9.5,
  }) {
    final tp = TextPainter(
      text: TextSpan(text: text, style: TextStyle(color: color, fontSize: fontSize)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, offset);
  }

  @override
  bool shouldRepaint(covariant CandleChartPainter oldDelegate) => true;
}
