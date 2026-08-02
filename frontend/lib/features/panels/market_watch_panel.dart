/// Market Watch panel — symbols, bid/ask/spread/change.
///
/// Phase 2 wires this to the real-time market data provider. Until then the
/// table structure is real but values are marked unavailable (no fake data).
library;

import 'package:flutter/material.dart';

import '../../app/theme.dart';

class MarketWatchPanel extends StatefulWidget {
  const MarketWatchPanel({super.key});

  @override
  State<MarketWatchPanel> createState() => _MarketWatchPanelState();
}

class _MarketWatchPanelState extends State<MarketWatchPanel> {
  String _query = '';

  static const _watchlist = [
    'XAUUSD',
    'EURUSD',
    'GBPUSD',
    'USDJPY',
    'BTCUSD',
    'NAS100',
  ];

  @override
  Widget build(BuildContext context) {
    final matches = _watchlist.where((s) => s.contains(_query.toUpperCase())).toList();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(6),
          child: TextField(
            onChanged: (v) => setState(() => _query = v),
            decoration: const InputDecoration(
              hintText: 'Search symbols…',
              prefixIcon: Icon(Icons.search, size: 16),
              contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 6),
            ),
          ),
        ),
        Row(
          children: const [
            Expanded(flex: 3, child: _Header('Symbol')),
            Expanded(flex: 2, child: _Header('Bid')),
            Expanded(flex: 2, child: _Header('Ask')),
            Expanded(flex: 1, child: _Header('Sprd')),
            Expanded(flex: 2, child: _Header('Chg %')),
          ],
        ),
        const Divider(height: 1),
        Expanded(
          child: ListView.separated(
            itemCount: matches.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final symbol = matches[index];
              return _SymbolRow(symbol: symbol, connected: false);
            },
          ),
        ),
        const Divider(height: 1),
        const Padding(
          padding: EdgeInsets.all(6),
          child: Text(
            'Market data: not connected — Phase 2 (simulated provider)',
            style: TextStyle(color: EntryXColors.textDim, fontSize: 10),
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
  const _SymbolRow({required this.symbol, required this.connected});

  final String symbol;
  final bool connected;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () {
        // Phase 3: switch the active chart to this symbol.
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 5),
        child: Row(
          children: [
            Expanded(flex: 3, child: Text(symbol, style: const TextStyle(fontSize: 11))),
            Expanded(flex: 2, child: _cell('--')),
            Expanded(flex: 2, child: _cell('--')),
            Expanded(flex: 1, child: _cell('--')),
            Expanded(flex: 2, child: _cell('--', color: EntryXColors.textDim)),
          ],
        ),
      ),
    );
  }

  Widget _cell(String text, {Color? color}) => Text(
        text,
        style: TextStyle(fontSize: 11, color: color ?? EntryXColors.textDim),
        textAlign: TextAlign.end,
      );
}
