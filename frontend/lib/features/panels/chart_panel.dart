/// Chart panel — real canvas engine surface.
///
/// Toolbar (symbol, timeframe, indicators, follow/reset), the CustomPainter
/// chart with pan/zoom/crosshair gestures, and a legend bar with the active
/// bar's OHLC plus overlay chips.
library;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app/theme.dart';
import '../chart/candle_painter.dart';
import '../chart/chart_models.dart';
import '../chart/chart_store.dart';
import '../market/market_watch_store.dart';

class ChartPanel extends StatelessWidget {
  const ChartPanel({super.key});

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
        Expanded(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final chartWidth = constraints.maxWidth - CandleChartPainter.priceWidth;
              final visibleCount = store.visibleEnd - store.visibleStart;
              final barWidth = visibleCount > 0 && chartWidth > 0 ? chartWidth / visibleCount : 1.0;

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
                    if (visibleCount <= 0) return;
                    final index = store.visibleStart +
                        (details.localPosition.dx / barWidth)
                            .floor()
                            .clamp(0, visibleCount - 1)
                            .toInt();
                    final midY = details.localPosition.dy;
                    final price = _priceAtY(store, midY, constraints.maxHeight);
                    store.setCrosshair(index, price);
                  },
                  child: GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onHorizontalDragUpdate: (details) {
                      store.panBy((details.delta.dx / barWidth).round());
                    },
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
                        connected: true,
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

  /// Maps a canvas y position back to a price using the same geometry as the painter.
  double _priceAtY(ChartStore store, double y, double height) {
    final candles = store.candles;
    if (candles.isEmpty) return 0;
    var minP = double.infinity;
    var maxP = double.negativeInfinity;
    for (var i = store.visibleStart; i < store.visibleEnd && i < candles.length; i++) {
      final c = candles[i];
      if (c.low < minP) minP = c.low;
      if (c.h > maxP) maxP = c.h;
    }
    if (!minP.isFinite) return 0;
    final pad = (maxP - minP) * 0.06;
    minP -= pad;
    maxP += pad;
    if (maxP <= minP) maxP = minP + 1;
    final chartBottom = height - CandleChartPainter.timeHeight;
    final volume = chartBottom * 0.22;
    final priceBottom = chartBottom - volume;
    return maxP - (y - 0) / (priceBottom - 0) * (maxP - minP);
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
