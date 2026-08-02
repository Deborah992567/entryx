/// EntryX top bar: logo, menus, connection status, account, balance.
library;

import 'package:flutter/material.dart';

import '../../app/theme.dart';
import '../../core/models.dart';
import 'system_status_store.dart';

class TopBar extends StatelessWidget {
  const TopBar({
    super.key,
    required this.user,
    required this.statusStore,
    required this.onLogout,
  });

  final User? user;
  final SystemStatusStore statusStore;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 40,
      decoration: const BoxDecoration(
        color: EntryXColors.bgRaised,
        border: Border(bottom: BorderSide(color: EntryXColors.border)),
      ),
      child: Row(
        children: [
          const SizedBox(width: 10),
          const _Logo(),
          const SizedBox(width: 14),
          _Menu(label: 'File'),
          _Menu(label: 'View'),
          _Menu(label: 'Charts'),
          _Menu(label: 'Trading'),
          _Menu(label: 'AI'),
          _Menu(label: 'Tools'),
          _Menu(label: 'Settings'),
          const Spacer(),
          _ConnectionStatus(store: statusStore),
          const SizedBox(width: 14),
          if (user != null) ..._accountWidgets(context),
          const SizedBox(width: 8),
        ],
      ),
    );
  }

  List<Widget> _accountWidgets(BuildContext context) {
    return [
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: EntryXColors.bgSunken,
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: EntryXColors.border),
        ),
        child: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('PAPER', style: TextStyle(fontSize: 9, color: EntryXColors.gold, letterSpacing: 1)),
            Text('USD 100,000.00', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
      const SizedBox(width: 12),
      PopupMenuButton<String>(
        tooltip: 'Account',
        icon: Icon(Icons.account_circle, size: 20, color: EntryXColors.textDim),
        padding: EdgeInsets.zero,
        onSelected: (v) {
          if (v == 'logout') onLogout();
        },
        itemBuilder: (_) => [
          PopupMenuItem(
            enabled: false,
            child: Text(user!.email, style: const TextStyle(fontSize: 12)),
          ),
          const PopupMenuDivider(),
          const PopupMenuItem(value: 'logout', child: Text('Log out')),
        ],
      ),
    ];
  }
}

class _Logo extends StatelessWidget {
  const _Logo();

  @override
  Widget build(BuildContext context) {
    return const Row(
      children: [
        Icon(Icons.trending_up, size: 16, color: EntryXColors.accentBright),
        SizedBox(width: 6),
        Text(
          'ENTRYX',
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w800,
            letterSpacing: 1.5,
            color: EntryXColors.text,
          ),
        ),
      ],
    );
  }
}

class _Menu extends StatelessWidget {
  const _Menu({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () {
        // Command palette / menus arrive with their subsystems.
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        child: Text(label, style: const TextStyle(fontSize: 11, color: EntryXColors.textDim)),
      ),
    );
  }
}

class _ConnectionStatus extends StatelessWidget {
  const _ConnectionStatus({required this.store});

  final SystemStatusStore store;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final backendUp = store.backendUp;
        final wsUp = store.wsStatus.name == 'connected';
        final color = backendUp ? (wsUp ? EntryXColors.up : EntryXColors.warn) : EntryXColors.down;
        final label = backendUp
            ? (wsUp ? 'Connected' : 'WS reconnecting')
            : 'Offline';
        return Tooltip(
          message: 'Backend: ${backendUp ? 'up' : 'down'} · '
              'WS: ${store.wsStatus.name}',
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: color.withValues(alpha: 0.6)),
              color: color.withValues(alpha: 0.12),
            ),
            child: Row(
              children: [
                Icon(Icons.circle, size: 8, color: color),
                const SizedBox(width: 6),
                Text(label, style: TextStyle(fontSize: 10, color: color)),
              ],
            ),
          ),
        );
      },
    );
  }
}
