/// EntryX terminal shell: top bar + workspace + bottom status bar.
library;

import 'package:flutter/material.dart';

import '../../app/theme.dart';
import 'system_status_store.dart';
import 'top_bar.dart';
import 'workspace/workspace_store.dart';
import 'workspace/workspace_view.dart';
import '../auth/auth_store.dart';

class EntryXShell extends StatefulWidget {
  const EntryXShell({
    super.key,
    required this.auth,
    required this.statusStore,
    required this.workspace,
  });

  final AuthStore auth;
  final SystemStatusStore statusStore;
  final WorkspaceStore workspace;

  @override
  State<EntryXShell> createState() => _EntryXShellState();
}

class _EntryXShellState extends State<EntryXShell> {
  @override
  void initState() {
    super.initState();
    widget.workspace.load();
    widget.statusStore.start();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          TopBar(
            user: widget.auth.user,
            statusStore: widget.statusStore,
            onLogout: () => widget.auth.logout(),
          ),
          Expanded(
            child: ListenableBuilder(
              listenable: widget.workspace,
              builder: (context, _) => WorkspaceView(store: widget.workspace),
            ),
          ),
          const _StatusBar(),
        ],
      ),
    );
  }
}

class _StatusBar extends StatelessWidget {
  const _StatusBar();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 24,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: const BoxDecoration(
        color: EntryXColors.bgRaised,
        border: Border(top: BorderSide(color: EntryXColors.border)),
      ),
      child: const Row(
        children: [
          Icon(Icons.circle, size: 7, color: EntryXColors.textDim),
          SizedBox(width: 6),
          Text('Market data: Phase 2', style: TextStyle(fontSize: 10, color: EntryXColors.textDim)),
          SizedBox(width: 16),
          Icon(Icons.circle, size: 7, color: EntryXColors.textDim),
          SizedBox(width: 6),
          Text('Trading engine: Phase 4', style: TextStyle(fontSize: 10, color: EntryXColors.textDim)),
          Spacer(),
          Text('EntryX v0.1.0 · Phase 1', style: TextStyle(fontSize: 10, color: EntryXColors.textDim)),
        ],
      ),
    );
  }
}
