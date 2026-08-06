/// EntryX root widget: providers, auth gate, shell routing.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/token_store.dart';
import '../core/ws_client.dart';
import '../features/auth/auth_screen.dart';
import '../features/auth/auth_store.dart';
import '../features/chart/chart_store_registry.dart';
import '../features/market/market_watch_store.dart';
import '../features/shell/entryx_shell.dart';
import '../features/shell/system_status_store.dart';
import '../features/shell/workspace/workspace_store.dart';
import '../features/trading/trading_store.dart';
import 'theme.dart';

class EntryXApp extends StatefulWidget {
  const EntryXApp({super.key});

  @override
  State<EntryXApp> createState() => _EntryXAppState();
}

class _EntryXAppState extends State<EntryXApp> {
  late final TokenStore _tokens;
  late final ApiClient _api;
  late final WsClient _ws;
  late final AuthStore _auth;
  late final SystemStatusStore _status;
  late final WorkspaceStore _workspace;
  late final MarketWatchStore _marketWatch;
  late final ChartStoreRegistry _charts;
  late final TradingStore _trading;

  @override
  void initState() {
    super.initState();
    _tokens = TokenStore();
    _api = ApiClient(store: _tokens);
    _ws = WsClient(store: _tokens);
    _auth = AuthStore(api: _api, tokens: _tokens, ws: _ws);
    _status = SystemStatusStore(api: _api, ws: _ws);
    _workspace = WorkspaceStore(api: _api);
    _marketWatch = MarketWatchStore(api: _api, ws: _ws);
    _charts = ChartStoreRegistry(api: _api, ws: _ws);
    _trading = TradingStore(api: _api, ws: _ws, auth: _auth);
    _auth.restore();
  }

  @override
  void dispose() {
    _trading.dispose();
    _charts.dispose();
    _marketWatch.dispose();
    _workspace.dispose();
    _status.dispose();
    _auth.dispose();
    _ws.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'EntryX',
      debugShowCheckedModeBanner: false,
      theme: EntryXTheme.dark(),
      home: MultiProvider(
        providers: [
          Provider<ApiClient>.value(value: _api),
          ChangeNotifierProvider.value(value: _auth),
          ChangeNotifierProvider.value(value: _marketWatch),
          ChangeNotifierProvider.value(value: _charts),
          ChangeNotifierProvider.value(value: _workspace),
          ChangeNotifierProvider.value(value: _trading),
        ],
        child: ListenableBuilder(
          listenable: _auth,
          builder: (context, _) {
            return switch (_auth.status) {
              AuthStatus.unknown => const _BootSplash(),
              AuthStatus.authenticated =>
                EntryXShell(auth: _auth, statusStore: _status, workspace: _workspace),
              AuthStatus.unauthenticated => AuthScreen(store: _auth),
            };
          },
        ),
      ),
    );
  }
}

class _BootSplash extends StatelessWidget {
  const _BootSplash();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.trending_up, size: 40, color: EntryXColors.accentBright),
            SizedBox(height: 12),
            Text('ENTRYX',
                style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 3,
                    color: EntryXColors.text)),
            SizedBox(height: 8),
            SizedBox(
              width: 140,
              child: LinearProgressIndicator(
                minHeight: 2,
                backgroundColor: EntryXColors.bgRaised,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
