import 'package:entryx/core/api_client.dart';
import 'package:entryx/core/ws_client.dart';
import 'package:entryx/features/backtest/backtest_models.dart';
import 'package:entryx/features/chart/chart_models.dart';
import 'package:entryx/features/chart/chart_store.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> candleAt(DateTime ts) => {
      'symbol': 'XAUUSD',
      'timeframe': 'H1',
      'ts': ts.toUtc().toIso8601String(),
      'o': 100,
      'h': 102,
      'l': 99,
      'c': 100,
      'v': 10,
    };

class _FakeApi extends ApiClient {
  @override
  Future<dynamic> get(String path, {bool auth = true}) async {
    if (path.startsWith('/market/candles')) {
      final base = DateTime.utc(2026, 1, 1);
      return [for (var i = 0; i < 50; i++) candleAt(base.add(Duration(hours: i)))];
    }
    return null;
  }

  @override
  Future<dynamic> put(String path, {Object? body, bool auth = true}) async => null;
}

BacktestMetrics metrics() => const BacktestMetrics(
      startBalance: 10000,
      endBalance: 10090,
      netProfit: 90,
      totalTrades: 1,
      winningTrades: 1,
      losingTrades: 0,
      breakevenTrades: 0,
      winRate: 100,
      grossProfit: 10,
      grossLoss: 0,
      expectancy: 90,
      avgWin: 90,
      avgLoss: 0,
      largestWin: 90,
      largestLoss: 0,
      maxDrawdown: 0,
      maxDrawdownPct: 0,
      profitFactor: 10,
    );

void main() {
  late ChartStore store;
  late _FakeApi api;

  setUp(() {
    api = _FakeApi();
    store = ChartStore(api: api, ws: WsClient());
  });

  tearDown(() => store.dispose());

  Future<void> loaded() async {
    await Future<void>.delayed(Duration.zero);
    expect(store.candles, isNotEmpty);
  }

  test('setBacktest maps equity points and trade markers onto candle bars',
      () async {
    await loaded();
    final base = DateTime.utc(2026, 1, 1);
    final result = BacktestResult(
      id: 'bt1',
      strategy: 'ema_cross',
      symbol: 'XAUUSD',
      timeframe: 'H1',
      status: 'completed',
      metrics: metrics(),
      equityCurve: [
        for (var i = 0; i < 50; i++)
          EquityPoint(ts: base.add(Duration(hours: i)), equity: 1000.0 + i * 10),
      ],
      trades: [
        BacktestTrade(
          id: 't1',
          symbol: 'XAUUSD',
          side: 'buy',
          volume: 0.1,
          openPrice: 100.0,
          closePrice: 101.0,
          grossPnl: 10,
          netPnl: 9,
          commission: 1,
          swap: 0,
          openedAt: base.add(const Duration(hours: 10)).toIso8601String(),
          closedAt: base.add(const Duration(hours: 12)).toIso8601String(),
        ),
      ],
    );

    store.setBacktest(result);

    expect(store.backtest, same(result));
    expect(store.equitySeries, hasLength(50));
    expect(store.equitySeries[10], 1100.0);
    expect(store.equitySeries.first, 1000.0);
    expect(store.backtestMarkers, hasLength(2));
    expect(store.backtestMarkers[0].kind, TradeMarkerKind.entry);
    expect(store.backtestMarkers[0].buy, isTrue);
    expect(store.backtestMarkers[0].bar, 10);
    expect(store.backtestMarkers[1].kind, TradeMarkerKind.exit);
    expect(store.backtestMarkers[1].bar, 12);
  });

  test('clearBacktest removes the overlay', () async {
    await loaded();
    final base = DateTime.utc(2026, 1, 1);
    store.setBacktest(BacktestResult(
      id: 'bt1',
      strategy: 'ema_cross',
      symbol: 'XAUUSD',
      timeframe: 'H1',
      status: 'completed',
      metrics: metrics(),
      equityCurve: [EquityPoint(ts: base, equity: 1000)],
      trades: const [],
    ));
    expect(store.backtest, isNotNull);

    store.clearBacktest();

    expect(store.backtest, isNull);
    expect(store.equitySeries, isEmpty);
    expect(store.backtestMarkers, isEmpty);
  });

  test('switching symbol resets any overlaid backtest', () async {
    await loaded();
    final base = DateTime.utc(2026, 1, 1);
    store.setBacktest(BacktestResult(
      id: 'bt1',
      strategy: 'ema_cross',
      symbol: 'XAUUSD',
      timeframe: 'H1',
      status: 'completed',
      metrics: metrics(),
      equityCurve: [EquityPoint(ts: base, equity: 1000)],
      trades: const [],
    ));
    expect(store.backtest, isNotNull);

    await store.setSymbol('EURUSD');

    expect(store.backtest, isNull);
    expect(store.equitySeries, isEmpty);
    expect(store.backtestMarkers, isEmpty);
  });

  test('trade markers for bars outside the candle window are skipped',
      () async {
    await loaded();
    final base = DateTime.utc(2026, 1, 1);
    final result = BacktestResult(
      id: 'bt1',
      strategy: 'ema_cross',
      symbol: 'XAUUSD',
      timeframe: 'H1',
      status: 'completed',
      metrics: metrics(),
      equityCurve: const [],
      trades: [
        BacktestTrade(
          id: 't1',
          symbol: 'XAUUSD',
          side: 'sell',
          volume: 0.1,
          openPrice: 100.0,
          closePrice: 99.0,
          grossPnl: 10,
          netPnl: 9,
          commission: 1,
          swap: 0,
          openedAt: base.add(const Duration(hours: 5)).toIso8601String(),
          closedAt: base.add(const Duration(hours: 9999)).toIso8601String(),
        ),
      ],
    );

    store.setBacktest(result);

    expect(store.backtestMarkers, hasLength(1));
    expect(store.backtestMarkers.single.kind, TradeMarkerKind.entry);
    expect(store.backtestMarkers.single.buy, isFalse);
    expect(store.backtestMarkers.single.bar, 5);
  });

  test('BacktestResult parses metrics, equity curve, and trades', () {
    final json = {
      'id': 'bt-1',
      'strategy': 'ema_cross',
      'symbol': 'XAUUSD',
      'timeframe': 'H1',
      'status': 'completed',
      'metrics': {
        'start_balance': 10000,
        'end_balance': 10090,
        'net_profit': 90,
        'total_trades': 2,
        'winning_trades': 1,
        'losing_trades': 1,
        'breakeven_trades': 0,
        'win_rate': 50,
        'gross_profit': 100,
        'gross_loss': 10,
        'profit_factor': 10.0,
        'expectancy': 45,
        'avg_win': 100,
        'avg_loss': 10,
        'largest_win': 100,
        'largest_loss': 10,
        'max_drawdown': 5,
        'max_drawdown_pct': 0.05,
        'sharpe': 1.4,
      },
      'equity_curve': [
        {'ts': '2026-01-01T00:00:00Z', 'equity': 10000.0},
        {'ts': '2026-01-01T01:00:00Z', 'equity': 10090.0},
      ],
      'trades': [
        {
          'id': 't1',
          'symbol': 'XAUUSD',
          'side': 'buy',
          'volume': 0.1,
          'open_price': 100.0,
          'close_price': 101.0,
          'gross_pnl': 10.0,
          'net_pnl': 9.0,
          'commission': 1.0,
          'swap': 0.0,
          'opened_at': '2026-01-01T00:00:00Z',
          'closed_at': '2026-01-01T01:00:00Z',
          'open_bar': 0,
          'close_bar': 1,
        },
      ],
    };

    final result = BacktestResult.fromJson(json);

    expect(result.metrics.netProfit, 90);
    expect(result.metrics.profitFactor, 10.0);
    expect(result.equityCurve, hasLength(2));
    expect(result.equityCurve[1].equity, 10090.0);
    expect(result.trades.single.openBar, 0);
    expect(result.trades.single.closeBar, 1);
    expect(result.trades.single.side, 'buy');
  });

  test('OptimizationResult parses ranked results and overfit warnings', () {
    final json = {
      'id': 'opt-1',
      'strategy': 'ema_cross',
      'symbol': 'XAUUSD',
      'timeframe': 'H1',
      'metric': 'net_profit',
      'combinations': 9,
      'overfit_score': 62.5,
      'overfit_label': 'moderate',
      'warnings': ['Sample too small', 'Profit factor below 1.2'],
      'best': {'fast_ma': 21, 'slow_ma': 90},
      'results': [
        {
          'rank': 1,
          'params': {'fast_ma': 21, 'slow_ma': 90},
          'metrics': {
            'start_balance': 10000,
            'end_balance': 10100,
            'net_profit': 100,
            'total_trades': 30,
            'winning_trades': 18,
            'losing_trades': 12,
            'breakeven_trades': 0,
            'win_rate': 60,
            'gross_profit': 300,
            'gross_loss': 200,
            'profit_factor': 1.5,
            'expectancy': 3.33,
            'avg_win': 16.67,
            'avg_loss': 16.67,
            'largest_win': 50,
            'largest_loss': 30,
            'max_drawdown': 40,
            'max_drawdown_pct': 0.4,
          },
        },
      ],
    };

    final result = OptimizationResult.fromJson(json);

    expect(result.metric, 'net_profit');
    expect(result.overfitScore, 62.5);
    expect(result.overfitLabel, 'moderate');
    expect(result.warnings, hasLength(2));
    expect(result.results, hasLength(1));
    expect(result.results.first.rank, 1);
    expect(result.results.first.params['fast_ma'], 21);
    expect(result.best['slow_ma'], 90);
    expect(describeParams(result.results.first.params), contains('fast_ma=21'));
  });
}
