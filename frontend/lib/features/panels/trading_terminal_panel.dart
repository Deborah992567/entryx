/// Trading Terminal panel — tabbed positions/orders/history/account view.
///
/// Positions, Orders, History and Account tabs are wired to the live broker
/// through `TradingStore` (REST load + WebSocket events). Journal, Alerts,
/// Experts and Logs are honest placeholders for their later phases.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app/theme.dart';
import '../trading/trading_models.dart';
import '../trading/trading_store.dart';

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
    final store = context.watch<TradingStore>();
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
        Expanded(child: _body(store)),
      ],
    );
  }

  Widget _body(TradingStore store) {
    if (store.loading && store.account == null) {
      return const Center(
        child: SizedBox(
          width: 22,
          height: 22,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }
    if (store.error.isNotEmpty && store.account == null) {
      return _EmptyTab(message: store.error);
    }
    switch (_tab) {
      case 0:
        return _PositionsTab(store: store);
      case 1:
        return _OrdersTab(store: store);
      case 2:
        return _HistoryTab(store: store);
      case 3:
        return _AccountTab(account: store.account);
      case 4:
        return const _EmptyTab(message: 'No journal entries — journal analysis ships with AI features (Phase 8)');
      case 5:
        return const _EmptyTab(message: 'No alerts — alert engine is in a later phase');
      case 6:
        return const _EmptyTab(message: 'No experts — strategy engine in Phase 5');
      case 7:
        return const _LogsTab();
      default:
        return const _EmptyTab(message: 'No records');
    }
  }
}

// ---------------------------------------------------------------------------
// Positions
// ---------------------------------------------------------------------------

class _PositionsTab extends StatelessWidget {
  const _PositionsTab({required this.store});

  final TradingStore store;

  @override
  Widget build(BuildContext context) {
    final positions = store.positions;
    if (positions.isEmpty) {
      return const _EmptyTab(message: 'No open positions — place an order on the chart or via API');
    }
    return Column(
      children: [
        const Row(
          children: [
            _Col('Symbol', 72), _Col('Side', 50), _Col('Vol', 44),
            _Col('Open', 70), _Col('SL', 66), _Col('TP', 66),
            _Col('Trail', 52), _Col('P&L', 74, alignEnd: true), _Col('', 40),
          ],
        ),
        const Divider(height: 1),
        Expanded(
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SizedBox(
              width: 72 + 50 + 44 + 70 + 66 + 66 + 52 + 74 + 40,
              child: ListView.separated(
                itemCount: positions.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (context, index) => _PositionRow(
                  position: positions[index],
                  onClose: () => store.closePosition(positions[index].id),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _PositionRow extends StatelessWidget {
  const _PositionRow({required this.position, required this.onClose});

  final TradingPosition position;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final sideColor = position.side == 'buy' ? EntryXColors.up : EntryXColors.down;
    final pnlColor = position.floatingPnl >= 0 ? EntryXColors.up : EntryXColors.down;
    return Row(
      children: [
        _cell(position.symbol, width: 72),
        _cell(position.side.toUpperCase(), width: 50, color: sideColor),
        _cell(fmtVol(position.volume), width: 44),
        _cell(fmtPrice(position.openPrice), width: 70),
        _cell(position.sl == null ? '--' : fmtPrice(position.sl!), width: 66),
        _cell(position.tp == null ? '--' : fmtPrice(position.tp!), width: 66),
        _cell(position.trail == null ? '--' : fmtPrice(position.trail!), width: 52),
        _cell(fmtMoney(position.floatingPnl), width: 74, color: pnlColor, alignEnd: true),
        SizedBox(
          width: 40,
          height: 26,
          child: IconButton(
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            iconSize: 14,
            tooltip: 'Close position',
            icon: const Icon(Icons.close, color: EntryXColors.textDim),
            onPressed: onClose,
          ),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

class _OrdersTab extends StatelessWidget {
  const _OrdersTab({required this.store});

  final TradingStore store;

  @override
  Widget build(BuildContext context) {
    final orders = store.orders;
    if (orders.isEmpty) {
      return const _EmptyTab(message: 'No pending orders');
    }
    return Column(
      children: [
        const Row(
          children: [
            _Col('Symbol', 72), _Col('Side', 46), _Col('Type', 76),
            _Col('Vol', 44), _Col('Price', 66), _Col('Limit', 66),
            _Col('SL', 62), _Col('TP', 62), _Col('Expiry', 92), _Col('', 40),
          ],
        ),
        const Divider(height: 1),
        Expanded(
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SizedBox(
              width: 72 + 46 + 76 + 44 + 66 + 66 + 62 + 62 + 92 + 40,
              child: ListView.separated(
                itemCount: orders.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (context, index) => _OrderRow(
                  order: orders[index],
                  onCancel: () => store.cancelOrder(orders[index].id),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _OrderRow extends StatelessWidget {
  const _OrderRow({required this.order, required this.onCancel});

  final TradingOrder order;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final sideColor = order.side == 'buy' ? EntryXColors.up : EntryXColors.down;
    return Row(
      children: [
        _cell(order.symbol, width: 72),
        _cell(order.side.toUpperCase(), width: 46, color: sideColor),
        _cell(order.type, width: 76),
        _cell(fmtVol(order.volume), width: 44),
        _cell(order.price == null ? '--' : fmtPrice(order.price!), width: 66),
        _cell(order.limitPrice == null ? '--' : fmtPrice(order.limitPrice!), width: 66),
        _cell(order.sl == null ? '--' : fmtPrice(order.sl!), width: 62),
        _cell(order.tp == null ? '--' : fmtPrice(order.tp!), width: 62),
        _cell(order.expiry == null ? '--' : _shortTime(order.expiry!), width: 92),
        SizedBox(
          width: 40,
          height: 26,
          child: IconButton(
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            iconSize: 14,
            tooltip: 'Cancel order',
            icon: const Icon(Icons.cancel, color: EntryXColors.textDim),
            onPressed: onCancel,
          ),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------

class _HistoryTab extends StatelessWidget {
  const _HistoryTab({required this.store});

  final TradingStore store;

  @override
  Widget build(BuildContext context) {
    final history = store.history;
    if (history.isEmpty) {
      return const _EmptyTab(message: 'No closed trades yet');
    }
    return Column(
      children: [
        const Row(
          children: [
            _Col('Symbol', 72), _Col('Side', 46), _Col('Vol', 44),
            _Col('Open', 70), _Col('Close', 70), _Col('Net P&L', 78, alignEnd: true),
            _Col('Comm', 58), _Col('Swap', 56), _Col('Closed', 110),
          ],
        ),
        const Divider(height: 1),
        Expanded(
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SizedBox(
              width: 72 + 46 + 44 + 70 + 70 + 78 + 58 + 56 + 110,
              child: ListView.separated(
                itemCount: history.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (context, index) => _TradeRow(trade: history[index]),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _TradeRow extends StatelessWidget {
  const _TradeRow({required this.trade});

  final TradeRecord trade;

  @override
  Widget build(BuildContext context) {
    final sideColor = trade.side == 'buy' ? EntryXColors.up : EntryXColors.down;
    final pnlColor = trade.netPnl >= 0 ? EntryXColors.up : EntryXColors.down;
    return Row(
      children: [
        _cell(trade.symbol, width: 72),
        _cell(trade.side.toUpperCase(), width: 46, color: sideColor),
        _cell(fmtVol(trade.volume), width: 44),
        _cell(fmtPrice(trade.openPrice), width: 70),
        _cell(fmtPrice(trade.closePrice), width: 70),
        _cell(fmtMoney(trade.netPnl), width: 78, color: pnlColor, alignEnd: true),
        _cell(fmtMoney(trade.commission), width: 58, alignEnd: true),
        _cell(fmtMoney(trade.swap), width: 56, alignEnd: true),
        _cell(_shortTime(trade.closedAt), width: 110),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Account
// ---------------------------------------------------------------------------

class _AccountTab extends StatelessWidget {
  const _AccountTab({required this.account});

  final TradingAccount? account;

  @override
  Widget build(BuildContext context) {
    final a = account;
    if (a == null) {
      return const _EmptyTab(message: 'Account data unavailable');
    }
    final pnlColor = a.floatingPnl >= 0 ? EntryXColors.up : EntryXColors.down;
    final metrics = <String, String>{
      'Balance': fmtMoney(a.balance),
      'Equity': fmtMoney(a.equity),
      'Margin': fmtMoney(a.marginUsed),
      'Free margin': fmtMoney(a.freeMargin),
      'Margin level': a.marginLevel > 0 ? '${a.marginLevel.toStringAsFixed(2)}%' : '--',
      'Floating P&L': fmtMoney(a.floatingPnl),
      'Realized P&L': fmtMoney(a.realizedPnl),
      'Commission': fmtMoney(a.commission),
      'Swap': fmtMoney(a.swap),
      'Exposure': fmtMoney(a.exposure),
      'Number': a.number,
      'Currency': a.currency,
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
                Text(
                  entry.value,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: entry.key == 'Floating P&L' ? pnlColor : EntryXColors.text,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Logs (connection status — other subsystems come later)
// ---------------------------------------------------------------------------

class _LogsTab extends StatelessWidget {
  const _LogsTab();

  @override
  Widget build(BuildContext context) {
    final store = context.watch<TradingStore>();
    final status = store.connected ? 'Connected' : 'Disconnected';
    final statusColor = store.connected ? EntryXColors.up : EntryXColors.warn;
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _logLine('WS', status, color: statusColor),
          _logLine('Broker', store.account == null ? 'no data' : store.account!.number),
          _logLine('Loading', store.loading ? 'true' : 'false'),
          if (store.error.isNotEmpty) _logLine('Error', store.error, color: EntryXColors.down),
          const SizedBox(height: 8),
          const Text(
            'Full execution/decision logs stream here in a later phase.',
            style: TextStyle(fontSize: 10, color: EntryXColors.textDim),
          ),
        ],
      ),
    );
  }

  Widget _logLine(String key, String value, {Color color = EntryXColors.text}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(width: 70, child: Text(key,
              style: const TextStyle(fontSize: 11, color: EntryXColors.textDim))),
          Expanded(
            child: Text(value,
                style: TextStyle(fontSize: 11, color: color), overflow: TextOverflow.ellipsis),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Shared widgets and formatting helpers
// ---------------------------------------------------------------------------

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

class _Col extends StatelessWidget {
  const _Col(this.text, this.width, {this.alignEnd = false});
  final String text;
  final double width;
  final bool alignEnd;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
        child: Text(
          text,
          textAlign: alignEnd ? TextAlign.end : TextAlign.start,
          style: const TextStyle(fontSize: 10, color: EntryXColors.textDim),
        ),
      ),
    );
  }
}

Widget _cell(
  String text, {
  required double width,
  Color? color,
  bool alignEnd = false,
}) {
  return SizedBox(
    width: width,
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 5),
      child: Text(
        text,
        textAlign: alignEnd ? TextAlign.end : TextAlign.start,
        style: TextStyle(fontSize: 11, color: color ?? EntryXColors.text),
        overflow: TextOverflow.ellipsis,
      ),
    ),
  );
}

String fmtPrice(double value) {
  final abs = value.abs();
  return abs >= 100 ? value.toStringAsFixed(2) : value.toStringAsFixed(5);
}

String fmtVol(double value) => value.toStringAsFixed(2);

String fmtMoney(double value) {
  final sign = value < 0 ? '-' : '';
  return '$sign\$${value.abs().toStringAsFixed(2)}';
}

String _shortTime(String iso) {
  final parsed = DateTime.tryParse(iso);
  if (parsed == null) return iso;
  final local = parsed.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(local.day)}.${two(local.month)} ${two(local.hour)}:${two(local.minute)}';
}
