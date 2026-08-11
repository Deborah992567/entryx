/// Canvas chart engine: candlesticks, volume pane, price/time scales, grid,
/// indicator overlays, bands, persistent drawings, and a crosshair with OHLC
/// readout.
///
/// Pure rendering: geometry comes from [ChartGeometry], so the painter never
/// owns data or gesture state.
library;

import 'dart:math' as math;

import 'package:flutter/widgets.dart' hide Overlay;

import 'chart_geometry.dart';
import 'chart_models.dart' as models;
import 'chart_template.dart';

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
    this.drawings = const [],
    this.selectedDrawingId,
    this.draft,
    this.lastPrice,
    this.equitySeries = const [],
    this.markers = const [],
    this.template = ChartTemplate.dark,
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
  final List<models.ChartDrawing> drawings;
  final int? selectedDrawingId;
  final models.ChartDrawing? draft;
  final double? lastPrice;
  final List<double?> equitySeries;
  final List<models.TradeMarker> markers;
  final ChartTemplate template;

  @override
  void paint(Canvas canvas, Size size) {
    final geo = ChartGeometry(
      size: size,
      candles: candles,
      start: start,
      end: end,
      overlays: overlays,
      bands: bands,
      lastPrice: lastPrice,
      equitySeries: equitySeries,
    );
    if (size.width <= ChartGeometry.priceWidth || size.height <= ChartGeometry.timeHeight) {
      return;
    }
    if (!geo.hasData) {
      return;
    }

    _drawGridAndScale(canvas, geo);

    var maxV = 0.0;
    for (var i = start; i < end; i++) {
      if (candles[i].v > maxV) maxV = candles[i].v;
    }
    _drawVolume(canvas, geo, maxV);
    _drawCandles(canvas, geo);
    for (final b in bands) {
      _drawBands(canvas, geo, b);
    }
    for (final o in overlays) {
      _drawLine(canvas, geo, o.series, _colorForOverlay(o.label));
    }

    if (geo.hasEquityPane) {
      _drawEquityPane(canvas, geo);
    }
    _drawTradeMarkers(canvas, geo);

    if (lastPrice != null) {
      _drawLastPriceTag(canvas, geo, lastPrice!);
    }

    for (final d in drawings) {
      _drawDrawing(canvas, geo, d, selected: d.id == selectedDrawingId);
    }
    final currentDraft = draft;
    if (currentDraft != null) {
      _drawDrawing(canvas, geo, currentDraft, draft: true);
    }

    if (crosshairIndex != null) {
      _drawCrosshair(canvas, geo, crosshairIndex!, crosshairPrice);
    }

    _drawOhlc(canvas, geo, crosshairIndex ?? end - 1);
  }

  // ----------------------------------------------------------------------- scale

  void _drawGridAndScale(Canvas canvas, ChartGeometry geo) {
    final grid = Paint()
      ..color = template.grid.withValues(alpha: 0.55)
      ..strokeWidth = 0.5;
    final rect = geo.priceRect;

    final step = geo.niceStep((geo.maxPrice - geo.minPrice) / 6);
    final decimals = geo.decimalsFor(step);
    var price = (geo.minPrice / step).floorToDouble() * step;
    while (price <= geo.maxPrice) {
      final y = geo.yForPrice(price);
      canvas.drawLine(Offset(0, y), Offset(rect.width, y), grid);
      _drawText(canvas, price.toStringAsFixed(decimals), Offset(rect.width + 6, y - 6),
          template.axisText, fontSize: 9.5);
      price += step;
    }

    final barStep = math.max(1, (geo.visibleCount / 6).round());
    for (var i = start; i < end; i += barStep) {
      final x = geo.xForBar(i.toDouble());
      canvas.drawLine(Offset(x, 0), Offset(x, geo.chartHeight), grid);
      _drawText(canvas, _formatTime(candles[i].ts), Offset(x - 14, rect.bottom + 4),
          template.axisText, fontSize: 9.5);
    }
  }

  // --------------------------------------------------------------------- volume

  void _drawVolume(Canvas canvas, ChartGeometry geo, double maxV) {
    final rect = geo.volumeRect;
    final paint = Paint();
    for (var i = start; i < end; i++) {
      final candle = candles[i];
      final x = geo.xForBar(i.toDouble());
      final height = maxV <= 0 ? 0.0 : (candle.v / maxV) * rect.height;
      paint.color = (candle.isBullish ? template.up : template.down)
          .withValues(alpha: 0.55);
      final bodyWidth = math.max(1.0, math.min(14.0, geo.barWidth * 0.72));
      canvas.drawRect(
        Rect.fromLTRB(x - bodyWidth / 2, rect.bottom - height, x + bodyWidth / 2, rect.bottom),
        paint,
      );
    }
  }

  // --------------------------------------------------------------- equity pane

  void _drawEquityPane(Canvas canvas, ChartGeometry geo) {
    final min = geo.equityMin;
    final max = geo.equityMax;
    if (min == null || max == null) return;

    final edge = Paint()
      ..color = template.grid.withValues(alpha: 0.7)
      ..strokeWidth = 0.5;
    canvas.drawLine(Offset(0, geo.equityTop), Offset(geo.chartWidth, geo.equityTop), edge);
    canvas.drawLine(Offset(0, geo.equityBottom), Offset(geo.chartWidth, geo.equityBottom), edge);

    final fill = Paint()..color = template.accent.withValues(alpha: 0.12);
    final line = Paint()
      ..color = template.accent
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;

    final path = Path();
    final reverse = <Offset>[];
    var started = false;
    for (var i = start; i < end && i < equitySeries.length; i++) {
      final v = equitySeries[i];
      if (v == null) {
        started = false;
        continue;
      }
      final x = geo.xForBar(i.toDouble());
      final y = geo.yForEquity(v);
      if (!started) {
        path.moveTo(x, y);
        started = true;
      } else {
        path.lineTo(x, y);
      }
      reverse.add(Offset(x, y));
    }
    if (started && reverse.isNotEmpty) {
      final closePath = Path.from(path);
      closePath.lineTo(reverse.last.dx, geo.equityBottom);
      closePath.lineTo(reverse.first.dx, geo.equityBottom);
      closePath.close();
      canvas.drawPath(closePath, fill);
      canvas.drawPath(path, line);
    }

    final decimals = _moneyDecimals(max);
    _drawText(canvas, 'Equity', Offset(6, geo.equityTop + 2), template.axisText, fontSize: 9);
    _drawText(
        canvas,
        min.toStringAsFixed(decimals),
        Offset(geo.chartWidth + 4, geo.equityBottom - 9),
        template.axisText,
        fontSize: 8.5);
    _drawText(
        canvas,
        max.toStringAsFixed(decimals),
        Offset(geo.chartWidth + 4, geo.equityTop + 1),
        template.axisText,
        fontSize: 8.5);
  }

  void _drawTradeMarkers(Canvas canvas, ChartGeometry geo) {
    for (final marker in markers) {
      if (marker.bar < start || marker.bar >= end) continue;
      final x = geo.xForBar(marker.bar.toDouble());
      final y = geo.yForPrice(marker.price);
      if (marker.kind == models.TradeMarkerKind.entry) {
        _drawEntryMarker(canvas, x, y, buy: marker.buy);
      } else {
        _drawExitMarker(canvas, x, y, buy: marker.buy);
      }
    }
  }

  void _drawEntryMarker(Canvas canvas, double x, double y, {required bool buy}) {
    final color = buy ? template.up : template.down;
    final r = 6.0;
    final path = Path();
    if (buy) {
      path.moveTo(x - r, y);
      path.lineTo(x + r, y);
      path.lineTo(x, y - r);
    } else {
      path.moveTo(x - r, y);
      path.lineTo(x + r, y);
      path.lineTo(x, y + r);
    }
    path.close();
    final fill = Paint()..color = color;
    final stroke = Paint()
      ..color = const Color(0xFF0E1116)
      ..strokeWidth = 1;
    canvas.drawPath(path, stroke);
    canvas.drawPath(path, fill);
  }

  void _drawExitMarker(Canvas canvas, double x, double y, {required bool buy}) {
    final color = buy ? template.up : template.down;
    final stroke = Paint()
      ..color = color
      ..strokeWidth = 1.3
      ..style = PaintingStyle.stroke;
    canvas.drawCircle(Offset(x, y), 4.5, stroke);
    canvas.drawCircle(Offset(x, y), 2.2, Paint()..color = color);
  }

  int _moneyDecimals(double value) {
    final abs = value.abs();
    if (abs >= 1000) return 0;
    if (abs >= 10) return 1;
    return 2;
  }

  // -------------------------------------------------------------------- candles

  void _drawCandles(Canvas canvas, ChartGeometry geo) {
    final bodyWidth = math.max(1.0, math.min(14.0, geo.barWidth * 0.72));
    final wick = Paint()..strokeWidth = 1;
    final body = Paint();
    for (var i = start; i < end; i++) {
      final candle = candles[i];
      final color = candle.isBullish ? template.up : template.down;
      final x = geo.xForBar(i.toDouble());
      wick.color = color;
      canvas.drawLine(Offset(x, geo.yForPrice(candle.h)), Offset(x, geo.yForPrice(candle.low)), wick);
      final top = geo.yForPrice(math.max(candle.o, candle.c));
      final bottom = geo.yForPrice(math.min(candle.o, candle.c));
      body.color = color;
      canvas.drawRect(
        Rect.fromLTRB(x - bodyWidth / 2, top, x + bodyWidth / 2, math.max(bottom, top + 1)),
        body,
      );
    }
  }

  // -------------------------------------------------------------------- overlays

  void _drawBands(Canvas canvas, ChartGeometry geo, models.Bands bands) {
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
      final x = geo.xForBar(i.toDouble());
      if (!started) {
        path.moveTo(x, geo.yForPrice(u));
        started = true;
      } else {
        path.lineTo(x, geo.yForPrice(u));
      }
    }
    final reverse = <Offset>[];
    for (var i = end - 1; i >= start; i--) {
      final u = bands.upper[i];
      final l = bands.lower[i];
      if (u == null || l == null) continue;
      final x = geo.xForBar(i.toDouble());
      reverse.add(Offset(x, geo.yForPrice(l)));
    }
    if (started && reverse.isNotEmpty) {
      for (final o in reverse) {
        path.lineTo(o.dx, o.dy);
      }
      path.close();
      canvas.drawPath(path, fill);
    }
    _drawLine(canvas, geo, bands.mid, _colorForOverlay(bands.label));
    _drawLine(canvas, geo, bands.upper, _colorForOverlay(bands.label).withValues(alpha: 0.6));
    _drawLine(canvas, geo, bands.lower, _colorForOverlay(bands.label).withValues(alpha: 0.6));
  }

  void _drawLine(Canvas canvas, ChartGeometry geo, List<double?> series, Color color) {
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
      final x = geo.xForBar(i.toDouble());
      final y = geo.yForPrice(value);
      if (!started) {
        path.moveTo(x, y);
        started = true;
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, paint);
  }

  // ------------------------------------------------------------------- drawings

  void _drawDrawing(Canvas canvas, ChartGeometry geo, models.ChartDrawing drawing,
      {bool selected = false, bool draft = false}) {
    final color = drawing.color.withValues(alpha: draft ? 0.55 : 1.0);
    final paint = Paint()
      ..color = color
      ..strokeWidth = selected ? 1.6 : 1.1
      ..style = PaintingStyle.stroke;
    final decimals = geo.decimalsFor(geo.niceStep((geo.maxPrice - geo.minPrice) / 40));

    switch (drawing) {
      case models.TrendLineDrawing(:final p1, :final p2):
        canvas.drawLine(
            Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price)),
            Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price)),
            paint);
        if (selected) _drawHandles(canvas, geo, [p1, p2]);
      case models.RayDrawing(:final p1, :final p2):
        final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
        final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
        // extend to the right edge of the chart
        final direction = b - a;
        final t = direction.dx != 0 ? (geo.chartWidth - a.dx) / direction.dx : 0.0;
        final end = a + direction * math.max(t, 0);
        canvas.drawLine(a, end, paint);
        if (selected) _drawHandles(canvas, geo, [p1, p2]);
      case models.HorizontalLineDrawing(:final price):
        canvas.drawLine(
            Offset(0, geo.yForPrice(price)), Offset(geo.chartWidth, geo.yForPrice(price)), paint);
        _drawText(canvas, price.toStringAsFixed(decimals),
            Offset(geo.chartWidth + 4, geo.yForPrice(price) - 6), color, fontSize: 9.5);
      case models.VerticalLineDrawing(:final bar):
        canvas.drawLine(
            Offset(geo.xForBar(bar), 0), Offset(geo.xForBar(bar), geo.priceBottom), paint);
      case models.RectangleDrawing(:final p1, :final p2):
        final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
        final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
        canvas.drawRect(Rect.fromPoints(a, b), paint);
        if (selected) _drawHandles(canvas, geo, [p1, p2]);
      case models.ArrowDrawing(:final p1, :final p2):
        final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
        final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
        canvas.drawLine(a, b, paint);
        _drawArrowHead(canvas, a, b, color);
        if (selected) _drawHandles(canvas, geo, [p1, p2]);
      case models.ChannelDrawing(:final p1, :final p2, :final p3):
        final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
        final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
        final c = Offset(geo.xForBar(p3.bar), geo.yForPrice(p3.price));
        final v = b - a;
        _drawInfiniteLine(canvas, geo, a, v, paint);
        _drawInfiniteLine(canvas, geo, c, v, paint);
        if (selected) _drawHandles(canvas, geo, [p1, p2, p3]);
      case models.EllipseDrawing(:final p1, :final p2):
        final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
        final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
        canvas.drawOval(Rect.fromPoints(a, b), paint);
        if (selected) _drawHandles(canvas, geo, [p1, p2]);
      case models.TextDrawing(:final p1, :final text):
        final origin = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
        _drawText(canvas, text, origin - const Offset(0, 13), color, fontSize: 12);
        if (selected) _drawHandles(canvas, geo, [p1]);
      case models.FibFanDrawing(:final p1, :final p2):
        final origin = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
        for (final f in models.FibFanDrawing.levels) {
          final price = p1.price - (p1.price - p2.price) * f;
          final through = Offset(geo.xForBar(p2.bar), geo.yForPrice(price));
          _drawRay(canvas, geo, origin, through, paint);
        }
        if (selected) _drawHandles(canvas, geo, [p1, p2]);
      case models.FibExtensionDrawing(:final p1, :final p2):
        final left = geo.xForBar(p1.bar < p2.bar ? p1.bar : p2.bar);
        final right = geo.xForBar(p1.bar < p2.bar ? p2.bar : p1.bar);
        for (final f in models.FibExtensionDrawing.levels) {
          final price = p1.price + (p2.price - p1.price) * f;
          final y = geo.yForPrice(price);
          canvas.drawLine(Offset(left, y), Offset(right, y), paint);
          _drawText(
              canvas,
              '${(f * 100).round()}%  ${price.toStringAsFixed(decimals)}',
              Offset(right + 4, y - 6),
              color,
              fontSize: 9.5);
        }
        if (selected) _drawHandles(canvas, geo, [p1, p2]);
      case models.PitchforkDrawing(:final p1, :final p2, :final p3):
        final a = Offset(geo.xForBar(p1.bar), geo.yForPrice(p1.price));
        final b = Offset(geo.xForBar(p2.bar), geo.yForPrice(p2.price));
        final c = Offset(geo.xForBar(p3.bar), geo.yForPrice(p3.price));
        final v = (b + c) / 2 - a;
        _drawInfiniteLine(canvas, geo, a, v, paint);
        _drawInfiniteLine(canvas, geo, b, v, paint);
        _drawInfiniteLine(canvas, geo, c, v, paint);
        if (selected) _drawHandles(canvas, geo, [p1, p2, p3]);
      case models.SRZoneDrawing(:final p1, :final p2):
        final top = p1.price >= p2.price ? p1.price : p2.price;
        final bottom = p1.price < p2.price ? p1.price : p2.price;
        final yTop = geo.yForPrice(top);
        final yBottom = geo.yForPrice(bottom);
        final fill = Paint()..color = color.withValues(alpha: 0.12);
        canvas.drawRect(Rect.fromLTRB(0, yTop, geo.chartWidth, yBottom), fill);
        canvas.drawLine(Offset(0, yTop), Offset(geo.chartWidth, yTop), paint);
        canvas.drawLine(Offset(0, yBottom), Offset(geo.chartWidth, yBottom), paint);
        _drawText(canvas, top.toStringAsFixed(decimals), Offset(geo.chartWidth + 4, yTop - 6),
            color, fontSize: 9.5);
        if (selected) _drawHandles(canvas, geo, [p1, p2]);
      case models.FibRetracementDrawing(:final high, :final low):
        final left = geo.xForBar(high.bar < low.bar ? high.bar : low.bar);
        final right = geo.xForBar(high.bar < low.bar ? low.bar : high.bar);
        for (final f in models.FibRetracementDrawing.levels) {
          final price = high.price - (high.price - low.price) * f;
          final y = geo.yForPrice(price);
          canvas.drawLine(Offset(left, y), Offset(right, y), paint);
          _drawText(
              canvas,
              '${(f * 100).round()}%  ${price.toStringAsFixed(decimals)}',
              Offset(right + 4, y - 6),
              color,
              fontSize: 9.5);
        }
        if (selected) _drawHandles(canvas, geo, [high, low]);
    }
  }

  void _drawHandles(Canvas canvas, ChartGeometry geo, List<models.ChartPoint> points) {
    final paint = Paint()..color = const Color(0xFFFFFFFF);
    final stroke = Paint()
      ..color = template.accent
      ..strokeWidth = 1;
    for (final p in points) {
      final o = Offset(geo.xForBar(p.bar), geo.yForPrice(p.price));
      final r = 3.0;
      canvas.drawCircle(o, r + 1, stroke);
      canvas.drawCircle(o, r, paint);
    }
  }

  void _drawArrowHead(Canvas canvas, Offset base, Offset tip, Color color) {
    final dir = tip - base;
    final len = dir.distance;
    if (len < 1) return;
    final u = dir / len;
    const arrowLen = 11.0;
    const spread = 0.42;
    final cos = math.cos(spread);
    final sin = math.sin(spread);
    final w1 = tip - Offset(u.dx * cos - u.dy * sin, u.dx * sin + u.dy * cos) * arrowLen;
    final w2 = tip - Offset(u.dx * cos + u.dy * sin, -u.dx * sin + u.dy * cos) * arrowLen;
    final head = Paint()
      ..color = color
      ..strokeWidth = 1.1
      ..style = PaintingStyle.stroke;
    canvas.drawLine(tip, w1, head);
    canvas.drawLine(tip, w2, head);
  }

  /// Draws the infinite line through [a] in direction [v], clipped to the chart.
  void _drawInfiniteLine(Canvas canvas, ChartGeometry geo, Offset a, Offset v, Paint paint) {
    if (v.distance < 0.5) return;
    if (v.dx == 0) {
      canvas.drawLine(Offset(a.dx, 0), Offset(a.dx, geo.priceBottom), paint);
      return;
    }
    final tLeft = -a.dx / v.dx;
    final tRight = (geo.chartWidth - a.dx) / v.dx;
    final t1 = tLeft < tRight ? tLeft : tRight;
    final t2 = tLeft < tRight ? tRight : tLeft;
    canvas.drawLine(a + v * t1, a + v * t2, paint);
  }

  /// Draws the ray from [origin] through [through], extending to the right edge.
  void _drawRay(Canvas canvas, ChartGeometry geo, Offset origin, Offset through, Paint paint) {
    final dir = through - origin;
    if (dir.distance < 0.5) return;
    if (dir.dx == 0) {
      canvas.drawLine(origin, Offset(origin.dx, geo.priceBottom), paint);
      return;
    }
    final t = (geo.chartWidth - origin.dx) / dir.dx;
    canvas.drawLine(origin, origin + dir * math.max(t, 0), paint);
  }

  // ------------------------------------------------------------------- crosshair

  void _drawCrosshair(Canvas canvas, ChartGeometry geo, int index, double? price) {
    final x = geo.xForBar(index.toDouble());
    final line = Paint()
      ..color = template.crosshair.withValues(alpha: 0.9)
      ..strokeWidth = 0.8;
    canvas.drawLine(Offset(x, 0), Offset(x, geo.priceBottom), line);

    final p = price ?? candles[index].c;
    final y = geo.yForPrice(p);
    canvas.drawLine(Offset(0, y), Offset(geo.chartWidth, y), line);

    final tag = Paint()..color = template.accent;
    final label = p.toStringAsFixed(geo.decimalsFor((geo.maxPrice - geo.minPrice) / 40));
    final tp = TextPainter(
      text: TextSpan(
        text: label,
        style: const TextStyle(color: Color(0xFFFFFFFF), fontSize: 9.5),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final tagRect = Rect.fromLTWH(geo.chartWidth + 1, y - 7, 34, 14);
    canvas.drawRect(tagRect, tag);
    tp.paint(canvas, Offset(geo.chartWidth + 6, y - 5.5));
  }

  void _drawLastPriceTag(Canvas canvas, ChartGeometry geo, double price) {
    final decimals = geo.decimalsFor(geo.niceStep((geo.priceBottom) / 60));
    final label = price.toStringAsFixed(decimals);
    final tp = TextPainter(
      text: TextSpan(text: label, style: const TextStyle(color: Color(0xFFFFFFFF), fontSize: 9.5)),
      textDirection: TextDirection.ltr,
    )..layout();
    final w = tp.width + 12;
    final paint = Paint()..color = template.accent;
    canvas.drawRect(Rect.fromLTWH(geo.chartWidth + 1, geo.yForPrice(price) - 7, w, 14), paint);
    tp.paint(canvas, Offset(geo.chartWidth + 7, geo.yForPrice(price) - 5.5));
  }

  // --------------------------------------------------------------------- OHLC

  void _drawOhlc(Canvas canvas, ChartGeometry geo, int index) {
    if (index < 0 || index >= candles.length) return;
    final c = candles[index];
    final color = c.isBullish ? template.up : template.down;
    final parts = <TextSpan>[
      TextSpan(
        text: symbol.isEmpty ? '' : '$symbol  ',
        style: TextStyle(color: template.axisText),
      ),
      TextSpan(
        text: 'O ${_price(c.o)}  H ${_price(c.h)}  L ${_price(c.low)}  C ${_price(c.c)}  ',
        style: TextStyle(color: color),
      ),
      TextSpan(text: 'V ${_vol(c.v)}', style: TextStyle(color: template.axisText)),
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

  String _formatTime(DateTime ts) {
    if (timeframe.isIntraday) {
      return '${_two(ts.hour)}:${_two(ts.minute)}';
    }
    return '${_two(ts.month)}/${_two(ts.day)}';
  }

  String _two(int v) => v.toString().padLeft(2, '0');

  Color _colorForOverlay(String label) => models.overlayColors[label] ?? template.accent;

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
