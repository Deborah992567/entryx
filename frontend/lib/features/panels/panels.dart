/// Panel registry: maps `PanelType` to its widget builder.
library;

import 'package:flutter/material.dart';

import '../shell/workspace/dock_layout.dart';
import 'ai_copilot_panel.dart';
import 'chart_panel.dart';
import 'market_watch_panel.dart';
import 'trading_terminal_panel.dart';

Widget buildPanel(PanelType type, {required String panelId}) {
  return switch (type) {
    PanelType.marketWatch => const MarketWatchPanel(),
    PanelType.chart => ChartPanel(storeKey: panelId),
    PanelType.aiCopilot => const AiCopilotPanel(),
    PanelType.terminal => const TradingTerminalPanel(),
    PanelType.journal => _NotBuiltPanel(title: 'Journal'),
    PanelType.alerts => _NotBuiltPanel(title: 'Alerts'),
    PanelType.positions => _NotBuiltPanel(title: 'Positions'),
    PanelType.history => _NotBuiltPanel(title: 'History'),
  };
}

/// Honest placeholder for panels whose subsystem is not built yet.
class _NotBuiltPanel extends StatelessWidget {
  const _NotBuiltPanel({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.construction, color: colors.primary.withValues(alpha: 0.6), size: 28),
          const SizedBox(height: 8),
          Text('$title — not built yet (later phase)',
              style: TextStyle(color: colors.onSurface.withValues(alpha: 0.5), fontSize: 12)),
        ],
      ),
    );
  }
}
