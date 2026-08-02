/// Trading Terminal panel — tabbed order/position/history view.
///
/// The trading engine (Phase 4) populates these tables. Until then the tab
/// structure and column layouts are real; rows are empty with an honest note.
library;

import 'package:flutter/material.dart';

import '../../app/theme.dart';

class TradingTerminalPanel extends StatefulWidget {
  const TradingTerminalPanel({super.key});

  @override
  State<TradingTerminalPanel> createState() => _TradingTerminalPanelState();
}

class _TradingTerminalPanelState extends State<TradingTerminalPanel> {
  int _tab = 0;

  static const _tabs = [
    ('Positions', Icons.candlestick_chart),
    ('Orders', Icons.pending_actions),
    ('History', Icons.history),
    ('Account', Icons.account_balance_wallet),
    ('Journal', Icons.edit_note),
    ('Alerts', Icons.notifications),
    ('Experts', Icons.memory),
    ('Logs', Icons.terminal),
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          height: 30,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 4),
            children: [
              for (var i = 0; i < _tabs.length; i++)
                _TabChip(
                  label: _tabs[i].$1,
                  icon: _tabs[i].$2,
                  selected: i == _tab,
                  onTap: () => setState(() => _tab = i),
                ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(child: _body()),
      ],
    );
  }

  Widget _body() {
    switch (_tab) {
      case 3:
        return const _AccountTab();
      case 5:
        return const _EmptyTab(message: 'No alerts — alert engine in Phase 4');
      case 6:
        return const _EmptyTab(message: 'No experts — strategy engine in Phase 5');
      case 7:
        return const _EmptyTab(message: 'Logs stream here once connected (Phase 4)');
      default:
        return const _EmptyTab(message: 'No records — trading engine in Phase 4');
    }
  }
}

class _TabChip extends StatelessWidget {
  const _TabChip({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 2, vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 10),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected ? EntryXColors.accent.withValues(alpha: 0.15) : Colors.transparent,
          borderRadius: BorderRadius.circular(4),
          border: Border.all(
            color: selected ? EntryXColors.accent : EntryXColors.border,
          ),
        ),
        child: Row(
          children: [
            Icon(icon, size: 12, color: selected ? EntryXColors.accentBright : EntryXColors.textDim),
            const SizedBox(width: 5),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                color: selected ? EntryXColors.text : EntryXColors.textDim,
                fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyTab extends StatelessWidget {
  const _EmptyTab({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.table_rows, color: EntryXColors.textDim.withValues(alpha: 0.6), size: 26),
          const SizedBox(height: 8),
          Text(message, style: const TextStyle(fontSize: 11, color: EntryXColors.textDim)),
        ],
      ),
    );
  }
}

class _AccountTab extends StatelessWidget {
  const _AccountTab();

  @override
  Widget build(BuildContext context) {
    final metrics = {
      'Balance': '--',
      'Equity': '--',
      'Margin': '--',
      'Free margin': '--',
      'Margin level': '--',
      'Floating P&L': '--',
      'Realized P&L': '--',
    };
    return GridView.count(
      crossAxisCount: 3,
      padding: const EdgeInsets.all(12),
      childAspectRatio: 2.4,
      children: [
        for (final entry in metrics.entries)
          Container(
            margin: const EdgeInsets.all(4),
            padding: const EdgeInsets.symmetric(horizontal: 10),
            decoration: BoxDecoration(
              color: EntryXColors.bgRaised,
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: EntryXColors.border),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(entry.key,
                    style: const TextStyle(fontSize: 10, color: EntryXColors.textDim)),
                const SizedBox(height: 2),
                Text(entry.value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              ],
            ),
          ),
      ],
    );
  }
}
