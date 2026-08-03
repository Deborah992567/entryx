/// Market Watch panel — symbols, bid/ask/spread/change/volume with live ticks,
/// search, category filter and favorites.
///
/// Data flows from the backend through `MarketWatchStore`: the REST catalog and
/// real-time `market.watch` / `market.tick` events. No fake values are shown.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app/theme.dart';
import '../../core/models.dart';
import '../market/market_watch_store.dart';

class MarketWatchPanel extends StatelessWidget {
  const MarketWatchPanel({super.key});

  @override
  Widget build(BuildContext context) {
    final store = context.watch<MarketWatchStore>();
    final symbols = store.visibleSymbols;

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(6, 6, 6, 4),
          child: TextField(
            onChanged: store.setQuery,
            decoration: const InputDecoration(
              hintText: 'Search symbols…',
              prefixIcon: Icon(Icons.search, size: 16),
              contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 6),
            ),
          ),
        ),
        SizedBox(
          height: 28,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 6),
            children: [
              for (final category in store.categories)
                Padding(
                  padding: const EdgeInsets.only(right: 4),
                  child: ChoiceChip(
                    label: Text(category.toUpperCase(),
                        style: const TextStyle(fontSize: 10)),
                    selected: store.category == category,
                    onSelected: (_) => store.setCategory(category),
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    labelPadding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                ),
            ],
          ),
        ),
        const Row(
          children: [
            Expanded(flex: 3, child: _Header('Symbol')),
            Expanded(flex: 2, child: _Header('Bid')),
            Expanded(flex: 2, child: _Header('Ask')),
            Expanded(flex: 1, child: _Header('Sprd')),
            Expanded(flex: 2, child: _Header('Chg %')),
            SizedBox(width: 24),
          ],
        ),
        const Divider(height: 1),
        Expanded(
          child: symbols.isEmpty
              ? const Center(
                  child: Text('No symbols match',
                      style: TextStyle(color: EntryXColors.textDim, fontSize: 11)),
                )
              : ListView.separated(
                  itemCount: symbols.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final symbol = symbols[index];
                    return _SymbolRow(
                      symbol: symbol,
                      quote: store.quoteFor(symbol.symbol),
                      favorite: store.isFavorite(symbol.symbol),
                      connected: store.connected,
                      onToggleFavorite: () => store.toggleFavorite(symbol.symbol),
                    );
                  },
                ),
        ),
        const Divider(height: 1),
        Padding(
          padding: const EdgeInsets.all(6),
          child: Text(
            store.error.isNotEmpty
                ? store.error
                : store.connected
                    ? 'Market data: live (simulated provider)'
                    : 'Market data: disconnected',
            style: const TextStyle(color: EntryXColors.textDim, fontSize: 10),
          ),
        ),
      ],
    );
  }
}

class _Header extends StatelessWidget {
  const _Header(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      child: Text(text, style: const TextStyle(fontSize: 10, color: EntryXColors.textDim)),
    );
  }
}

class _SymbolRow extends StatelessWidget {
  const _SymbolRow({
    required this.symbol,
    required this.quote,
    required this.favorite,
    required this.connected,
    required this.onToggleFavorite,
  });

  final SymbolInfo symbol;
  final Quote? quote;
  final bool favorite;
  final bool connected;
  final VoidCallback onToggleFavorite;

  @override
  Widget build(BuildContext context) {
    final q = quote;
    final color = q == null
        ? EntryXColors.textDim
        : q.changePct >= 0
            ? EntryXColors.up
            : EntryXColors.down;

    String fmt(double value) {
      final fixed = value.toStringAsFixed(symbol.digits.clamp(1, 5));
      return q == null ? '--' : fixed;
    }

    return InkWell(
      onTap: () {
        // Phase 3: switch the active chart to this symbol.
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 5),
        child: Row(
          children: [
            Expanded(flex: 3, child: Text(symbol.symbol,
                style: const TextStyle(fontSize: 11))),
            Expanded(flex: 2, child: _cell(fmt(q?.bid ?? 0))),
            Expanded(flex: 2, child: _cell(fmt(q?.ask ?? 0))),
            Expanded(flex: 1, child: _cell(q == null ? '--' : _spread(q.spread))),
            Expanded(
              flex: 2,
              child: _cell(q == null ? '--' : '${q.changePct.toStringAsFixed(2)}%',
                  color: color),
            ),
            IconButton(
              visualDensity: VisualDensity.compact,
              padding: EdgeInsets.zero,
              iconSize: 14,
              icon: Icon(favorite ? Icons.star : Icons.star_border,
                  color: favorite ? EntryXColors.accentBright : EntryXColors.textDim),
              onPressed: onToggleFavorite,
            ),
          ],
        ),
      ),
    );
  }

  String _spread(double spread) {
    if (spread <= 0) return '--';
    if (spread < 0.01) return spread.toStringAsExponential(0);
    return spread.toStringAsFixed(2);
  }

  Widget _cell(String text, {Color? color}) => Text(
        text,
        style: TextStyle(fontSize: 11, color: color ?? EntryXColors.textDim),
        textAlign: TextAlign.end,
      );
}
