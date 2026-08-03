/// Chart panel — real canvas engine surface.
///
/// Toolbar (symbol, timeframe, indicators, drawing tools), the CustomPainter
/// chart with pan/zoom/crosshair gestures plus drag-to-draw and move/select
/// drawing interactions, and a legend bar with OHLC + overlay chips.
library;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app/theme.dart';
import '../chart/candle_painter.dart';
import '../chart/chart_geometry.dart';
import '../chart/chart_models.dart';
import '../chart/chart_store.dart';
import '../market/market_watch_store.dart';

class ChartPanel extends StatefulWidget {
  const ChartPanel({super.key});

  @override
  State<ChartPanel> createState() => _ChartPanelState();
}

class _ChartPanelState extends State<ChartPanel> {
  ChartPoint? _pendingStart;
  ChartDrawing? _draft;
  ({ChartDrawing drawing, double bar, double price})? _moveState;

  @override
  Widget build(BuildContext context) {
    final store = context.watch<ChartStore>();
    final watch = context.watch<MarketWatchStore>();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      store.refreshIfNeeded();
    });

    final pack = store.buildIndicators();

    return Column(
      children: [
        _Toolbar(store: store, watch: watch),
        const Divider(height: 1),
        _DrawingToolbar(store: store),
        const Divider(height: 1),
        Expanded(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final geo = ChartGeometry(
                size: Size(constraints.maxWidth, constraints.maxHeight),
                candles: store.candles,
                start: store.visibleStart,
                end: store.visibleEnd,
                overlays: pack.overlays,
                bands: pack.bands,
              );
              final barWidth = geo.barWidth;

              return Listener(
                onPointerSignal: (event) {
                  if (event is PointerScrollEvent) {
                    if (event.scrollDelta.dy < 0) {
                      store.zoomIn();
                    } else {
                      store.zoomOut();
                    }
                  }
                },
                child: MouseRegion(
                  onExit: (_) => store.setCrosshair(null, null),
                  onHover: (details) {
                    if (!geo.hasData) return;
                    final index = store.visibleStart +
                        (details.localPosition.dx / barWidth)
                            .floor()
                            .clamp(0, geo.visibleCount - 1)
                            .toInt();
                    store.setCrosshair(index, geo.priceAtY(details.localPosition.dy));
                  },
                  child: GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onPanStart: (details) => _onPanStart(store, geo, details.localPosition),
                    onPanUpdate: (details) => _onPanUpdate(store, geo, details),
                    onPanEnd: (details) => _onPanEnd(store, geo),
                    onTapUp: (details) => _onTapUp(store, geo, details.localPosition),
                    onDoubleTapDown: (details) => store.resetView(),
                    child: CustomPaint(
                      painter: CandleChartPainter(
                        candles: store.candles,
                        start: store.visibleStart,
                        end: store.visibleEnd,
                        timeframe: store.timeframe,
                        symbol: store.symbol,
                        crosshairIndex: store.crosshairIndex,
                        crosshairPrice: store.crosshairPrice,
                        overlays: pack.overlays,
                        bands: pack.bands,
                        drawings: store.drawings,
                        selectedDrawingId: store.selectedDrawingId,
                        draft: _draft,
                      ),
                      size: Size(constraints.maxWidth, constraints.maxHeight),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        const Divider(height: 1),
        _LegendBar(store: store, watch: watch),
      ],
    );
  }

  void _onPanStart(ChartStore store, ChartGeometry geo, Offset pos) {
    if (!geo.hasData) return;
    final bar = geo.barAtX(pos.dx);
    final price = geo.priceAtY(pos.dy);

    if (store.tool == DrawingTool.select) {
      final hit = _hitTestDrawing(store, pos, geo);
      if (hit != null) {
        store.selectDrawing(hit.id);
        _moveState = (drawing: hit, bar: bar, price: price);
      } else {
        store.selectDrawing(null);
      }
      return;
    }

    final point = ChartPoint(bar, price);
    _pendingStart = point;
    _draft = _makeDraft(store.tool, -1, point);
    setState(() {});
  }

  void _onPanUpdate(ChartStore store, ChartGeometry geo, DragUpdateDetails details) {
    if (!geo.hasData) return;
    final move = _moveState;
    if (move != null) {
      final dBar = geo.barAtX(details.localPosition.dx) - move.bar;
      final dPrice = geo.priceAtY(details.localPosition.dy) - move.price;
      store.updateDrawing(move.drawing.translate(dBar, dPrice));
      return;
    }
    if (_draft != null) {
      final end = ChartPoint(geo.barAtX(details.localPosition.dx), geo.priceAtY(details.localPosition.dy));
      _draft = _makeDraft(store.tool, -1, _pendingStart ?? end, end);
      setState(() {});
      return;
    }
    if (store.tool == DrawingTool.select) {
      store.panBy((details.delta.dx / geo.barWidth).round());
    }
  }

  void _onPanEnd(ChartStore store, ChartGeometry geo) {
    final move = _moveState;
    if (move != null) {
      _moveState = null;
      return;
    }
    final draft = _draft;
    _draft = null;
    final start = _pendingStart;
    _pendingStart = null;
    if (draft == null) return;
    setState(() {});

    switch (draft) {
      case HorizontalLineDrawing():
        store.addDrawing(HorizontalLineDrawing(
            id: store.nextDrawingId, price: draft.price, color: draft.color));
      case VerticalLineDrawing():
        store.addDrawing(VerticalLineDrawing(
            id: store.nextDrawingId, bar: draft.bar, color: draft.color));
      case TrendLineDrawing():
        if (_dragDistance(geo, start!, draft.p2) >= 4) {
          store.addDrawing(TrendLineDrawing(
              id: store.nextDrawingId, p1: start, p2: draft.p2, color: draft.color));
        }
      case RayDrawing():
        if (_dragDistance(geo, start!, draft.p2) >= 4) {
          store.addDrawing(RayDrawing(
              id: store.nextDrawingId, p1: start, p2: draft.p2, color: draft.color));
        }
      case RectangleDrawing():
        if (_dragDistance(geo, start!, draft.p2) >= 4) {
          store.addDrawing(RectangleDrawing(
              id: store.nextDrawingId, p1: start, p2: draft.p2, color: draft.color));
        }
      case FibRetracementDrawing():
        if (_dragDistance(geo, start!, draft.p2) >= 4) {
          store.addDrawing(FibRetracementDrawing(
              id: store.nextDrawingId, p1: start, p2: draft.p2, color: draft.color));
        }
    }
  }

  void _onTapUp(ChartStore store, ChartGeometry geo, Offset pos) {
    if (store.tool != DrawingTool.select) return;
    final hit = _hitTestDrawing(store, pos, geo);
    store.selectDrawing(hit?.id);
  }

  double _dragDistance(ChartGeometry geo, ChartPoint a, ChartPoint b) {
    final p = Offset(geo.xForBar(a.bar), geo.yForPrice(a.price));
    final q = Offset(geo.xForBar(b.bar), geo.yForPrice(b.price));
    return (p - q).distance;
  }

  ChartDrawing _makeDraft(DrawingTool tool, int id, ChartPoint a, [ChartPoint? b]) {
    final p2 = b ?? a;
    switch (tool) {
      case DrawingTool.trendLine:
        return TrendLineDrawing(id: id, p1: a, p2: p2);
      case DrawingTool.ray:
        return RayDrawing(id: id, p1: a, p2: p2);
      case DrawingTool.horizontal:
        return HorizontalLineDrawing(id: id, price: a.price);
      case DrawingTool.vertical:
        return VerticalLineDrawing(id: id, bar: a.bar);
      case DrawingTool.rectangle:
        return RectangleDrawing(id: id, p1: a, p2: p2);
      case DrawingTool.fibonacci:
        return FibRetracementDrawing(id: id, p1: a, p2: p2);
      case DrawingTool.select:
        throw StateError('select tool has no draft');
    }
  }

  ChartDrawing? _hitTestDrawing(ChartStore store, Offset pos, ChartGeometry geo) {
    final selected = store.selectedDrawing;
    if (selected != null && selected.hitTest(pos, geo)) return selected;
    for (final d in store.drawings.reversed) {
      if (d.hitTest(pos, geo)) return d;
    }
    return null;
  }
}

class _Toolbar extends StatelessWidget {
  const _Toolbar({required this.store, required this.watch});

  final ChartStore store;
  final MarketWatchStore watch;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 34,
      child: Row(
        children: [
          const SizedBox(width: 8),
          _SymbolSelector(store: store, watch: watch),
          const SizedBox(width: 8),
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (final tf in Timeframe.values) ...[
                    ChoiceChip(
                      label: Text(tf.api,
                          style: TextStyle(
                            fontSize: 10,
                            color: store.timeframe == tf
                                ? Colors.black
                                : EntryXColors.textDim,
                          )),
                      selected: store.timeframe == tf,
                      onSelected: (_) => store.setTimeframe(tf),
                      visualDensity: VisualDensity.compact,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 0),
                      backgroundColor: EntryXColors.bgRaised,
                      selectedColor: EntryXColors.accentBright,
                      side: const BorderSide(color: EntryXColors.border, width: 0.5),
                      showCheckmark: false,
                    ),
                    const SizedBox(width: 4),
                  ],
                ],
              ),
            ),
          ),
          _IndicatorMenu(store: store),
          const SizedBox(width: 6),
          IconButton(
            onPressed: store.refresh,
            icon: const Icon(Icons.refresh, size: 14, color: EntryXColors.textDim),
            tooltip: 'Reload candles',
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 26, minHeight: 26),
          ),
          const SizedBox(width: 8),
        ],
      ),
    );
  }
}

class _DrawingToolbar extends StatelessWidget {
  const _DrawingToolbar({required this.store});

  final ChartStore store;

  static const Map<DrawingTool, IconData> icons = {
    DrawingTool.select: Icons.ads_click,
    DrawingTool.trendLine: Icons.timeline,
    DrawingTool.ray: Icons.north_east,
    DrawingTool.horizontal: Icons.remove,
    DrawingTool.vertical: Icons.line_weight,
    DrawingTool.rectangle: Icons.crop_square,
    DrawingTool.fibonacci: Icons.show_chart,
  };

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 30,
      child: Row(
        children: [
          const SizedBox(width: 8),
          for (final tool in DrawingTool.values) ...[
            InkWell(
              onTap: () => store.setTool(tool),
              child: Container(
                width: 26,
                height: 22,
                decoration: BoxDecoration(
                  color: store.tool == tool ? EntryXColors.accentBright.withValues(alpha: 0.25) : null,
                  borderRadius: BorderRadius.circular(3),
                ),
                child: Tooltip(
                  message: tool.label,
                  child: Icon(
                    icons[tool],
                    size: 13,
                    color: store.tool == tool ? EntryXColors.accentBright : EntryXColors.textDim,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 2),
          ],
          const SizedBox(width: 8),
          IconButton(
            onPressed: store.selectedDrawingId != null ? store.removeSelectedDrawing : null,
            icon: const Icon(Icons.delete_outline, size: 14, color: EntryXColors.textDim),
            tooltip: 'Delete selected drawing',
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
          ),
          IconButton(
            onPressed: store.drawings.isEmpty ? null : store.clearDrawings,
            icon: const Icon(Icons.delete_sweep_outlined, size: 14, color: EntryXColors.textDim),
            tooltip: 'Clear all drawings',
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
          ),
          const Spacer(),
          if (store.tool != DrawingTool.select)
            Text(
              '${store.tool.label} — drag on the chart',
              style: const TextStyle(fontSize: 10, color: EntryXColors.textDim),
            )
          else if (store.selectedDrawing != null)
            Text(
              'drawing selected — drag to move, Delete to remove',
              style: const TextStyle(fontSize: 10, color: EntryXColors.warn),
            ),
          const SizedBox(width: 8),
        ],
      ),
    );
  }
}

class _SymbolSelector extends StatelessWidget {
  const _SymbolSelector({required this.store, required this.watch});

  final ChartStore store;
  final MarketWatchStore watch;

  @override
  Widget build(BuildContext context) {
    final symbols = watch.symbols;
    if (symbols.isEmpty) {
      return Text(store.symbol,
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600));
    }
    return DropdownButton<String>(
      value: store.symbol,
      items: [
        for (final s in symbols)
          DropdownMenuItem(value: s.symbol, child: Text(s.symbol, style: const TextStyle(fontSize: 12))),
      ],
      onChanged: (v) {
        if (v != null) store.setSymbol(v);
      },
      underline: const SizedBox.shrink(),
      style: const TextStyle(color: EntryXColors.text, fontSize: 12, fontWeight: FontWeight.w600),
      dropdownColor: EntryXColors.bgRaised,
    );
  }
}

class _IndicatorMenu extends StatelessWidget {
  const _IndicatorMenu({required this.store});

  final ChartStore store;

  static const Map<String, String> labels = {
    'sma20': 'SMA 20',
    'sma50': 'SMA 50',
    'ema20': 'EMA 20',
    'vwap': 'VWAP',
    'bollinger': 'Bollinger',
  };

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      onSelected: store.toggleIndicator,
      tooltip: 'Indicators',
      icon: const Icon(Icons.functions, size: 15, color: EntryXColors.textDim),
      color: EntryXColors.bgRaised,
      itemBuilder: (context) => [
        for (final entry in labels.entries)
          CheckedPopupMenuItem<String>(
            value: entry.key,
            checked: store.indicatorEnabled(entry.key),
            child: Text(entry.value, style: const TextStyle(fontSize: 12)),
          ),
      ],
    );
  }
}

class _LegendBar extends StatelessWidget {
  const _LegendBar({required this.store, required this.watch});

  final ChartStore store;
  final MarketWatchStore watch;

  @override
  Widget build(BuildContext context) {
    final active = store.activeBarIndex;
    final quote = watch.quoteFor(store.symbol);
    final last = quote?.ask ?? (active != null && active < store.candles.length
        ? store.candles[active].c
        : null);

    return Container(
      height: 22,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      color: EntryXColors.bgRaised,
      child: Row(
        children: [
          if (store.loading) ...[
            const SizedBox(
              width: 10,
              height: 10,
              child: CircularProgressIndicator(strokeWidth: 1.5),
            ),
            const SizedBox(width: 6),
            const Text('Loading…', style: TextStyle(fontSize: 10, color: EntryXColors.textDim)),
          ] else if (store.error.isNotEmpty) ...[
            Icon(Icons.error_outline, size: 12, color: EntryXColors.down),
            const SizedBox(width: 6),
            Flexible(
              child: Text(store.error,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 10, color: EntryXColors.down)),
            ),
          ] else ...[
            const Icon(Icons.candlestick_chart, size: 13, color: EntryXColors.textDim),
            const SizedBox(width: 6),
            Text('${store.candles.length} bars',
                style: const TextStyle(fontSize: 10, color: EntryXColors.textDim)),
            const SizedBox(width: 10),
            if (last != null)
              Text(
                '${store.symbol} ${last.toStringAsFixed(5)}',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: (quote?.bid ?? last) <= last ? EntryXColors.up : EntryXColors.down,
                ),
              ),
            const SizedBox(width: 10),
            if (!store.followingLatest)
              const Text('panned · double-click to reset',
                  style: TextStyle(fontSize: 10, color: EntryXColors.warn)),
          ],
          const Spacer(),
          for (final key in store.indicatorKeys)
            if (store.indicatorEnabled(key))
              Padding(
                padding: const EdgeInsets.only(left: 8),
                child: Text(
                  _IndicatorMenu.labels[key]!,
                  style: TextStyle(fontSize: 10, color: overlayColors[_IndicatorMenu.labels[key]]),
                ),
              ),
        ],
      ),
    );
  }
}
