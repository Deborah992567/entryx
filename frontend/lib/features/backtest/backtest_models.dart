/// Backtest + optimizer domain models parsed from the backend REST contracts.
///
/// Nothing is computed client-side: every value mirrors `app.schemas.backtest`
/// on the server, so the UI stays an honest view of what the engine produced.
library;

class StrategyInfo {
  const StrategyInfo({
    required this.name,
    required this.description,
    required this.params,
  });

  final String name;
  final String description;
  final Map<String, dynamic> params;

  factory StrategyInfo.fromJson(Map<String, dynamic> json) => StrategyInfo(
        name: json['name'] as String,
        description: json['description'] as String? ?? '',
        params: (json['params'] as Map<String, dynamic>?) ?? const {},
      );
}

class BacktestMetrics {
  const BacktestMetrics({
    required this.startBalance,
    required this.endBalance,
    required this.netProfit,
    required this.totalTrades,
    required this.winningTrades,
    required this.losingTrades,
    required this.breakevenTrades,
    required this.winRate,
    required this.grossProfit,
    required this.grossLoss,
    required this.expectancy,
    required this.avgWin,
    required this.avgLoss,
    required this.largestWin,
    required this.largestLoss,
    required this.maxDrawdown,
    required this.maxDrawdownPct,
    this.profitFactor,
    this.sharpe,
    this.error,
  });

  final double startBalance;
  final double endBalance;
  final double netProfit;
  final int totalTrades;
  final int winningTrades;
  final int losingTrades;
  final int breakevenTrades;
  final double winRate;
  final double grossProfit;
  final double grossLoss;
  final double expectancy;
  final double avgWin;
  final double avgLoss;
  final double largestWin;
  final double largestLoss;
  final double maxDrawdown;
  final double maxDrawdownPct;
  final double? profitFactor;
  final double? sharpe;
  final String? error;

  factory BacktestMetrics.fromJson(Map<String, dynamic> json) => BacktestMetrics(
        startBalance: (json['start_balance'] as num).toDouble(),
        endBalance: (json['end_balance'] as num).toDouble(),
        netProfit: (json['net_profit'] as num).toDouble(),
        totalTrades: (json['total_trades'] as num).toInt(),
        winningTrades: (json['winning_trades'] as num).toInt(),
        losingTrades: (json['losing_trades'] as num).toInt(),
        breakevenTrades: (json['breakeven_trades'] as num).toInt(),
        winRate: (json['win_rate'] as num).toDouble(),
        grossProfit: (json['gross_profit'] as num).toDouble(),
        grossLoss: (json['gross_loss'] as num).toDouble(),
        expectancy: (json['expectancy'] as num).toDouble(),
        avgWin: (json['avg_win'] as num).toDouble(),
        avgLoss: (json['avg_loss'] as num).toDouble(),
        largestWin: (json['largest_win'] as num).toDouble(),
        largestLoss: (json['largest_loss'] as num).toDouble(),
        maxDrawdown: (json['max_drawdown'] as num).toDouble(),
        maxDrawdownPct: (json['max_drawdown_pct'] as num).toDouble(),
        profitFactor: (json['profit_factor'] as num?)?.toDouble(),
        sharpe: (json['sharpe'] as num?)?.toDouble(),
        error: json['error'] as String?,
      );
}

class BacktestTrade {
  const BacktestTrade({
    required this.id,
    required this.symbol,
    required this.side,
    required this.volume,
    required this.openPrice,
    required this.closePrice,
    required this.grossPnl,
    required this.netPnl,
    required this.commission,
    required this.swap,
    required this.openedAt,
    required this.closedAt,
    this.openBar,
    this.closeBar,
  });

  final String id;
  final String symbol;
  final String side;
  final double volume;
  final double openPrice;
  final double closePrice;
  final double grossPnl;
  final double netPnl;
  final double commission;
  final double swap;
  final String openedAt;
  final String closedAt;
  final int? openBar;
  final int? closeBar;

  factory BacktestTrade.fromJson(Map<String, dynamic> json) => BacktestTrade(
        id: json['id'] as String,
        symbol: json['symbol'] as String,
        side: json['side'] as String,
        volume: (json['volume'] as num).toDouble(),
        openPrice: (json['open_price'] as num).toDouble(),
        closePrice: (json['close_price'] as num).toDouble(),
        grossPnl: (json['gross_pnl'] as num).toDouble(),
        netPnl: (json['net_pnl'] as num).toDouble(),
        commission: (json['commission'] as num).toDouble(),
        swap: (json['swap'] as num).toDouble(),
        openedAt: json['opened_at'] as String,
        closedAt: json['closed_at'] as String,
        openBar: (json['open_bar'] as num?)?.toInt(),
        closeBar: (json['close_bar'] as num?)?.toInt(),
      );
}

class EquityPoint {
  const EquityPoint({required this.ts, required this.equity});

  final DateTime ts;
  final double equity;

  factory EquityPoint.fromJson(Map<String, dynamic> json) => EquityPoint(
        ts: DateTime.parse(json['ts'] as String),
        equity: (json['equity'] as num).toDouble(),
      );
}

class BacktestResult {
  const BacktestResult({
    required this.id,
    required this.strategy,
    required this.symbol,
    required this.timeframe,
    required this.status,
    required this.metrics,
    required this.equityCurve,
    required this.trades,
  });

  final String id;
  final String strategy;
  final String symbol;
  final String timeframe;
  final String status;
  final BacktestMetrics metrics;
  final List<EquityPoint> equityCurve;
  final List<BacktestTrade> trades;

  factory BacktestResult.fromJson(Map<String, dynamic> json) => BacktestResult(
        id: json['id'] as String,
        strategy: json['strategy'] as String,
        symbol: json['symbol'] as String,
        timeframe: json['timeframe'] as String,
        status: json['status'] as String,
        metrics: BacktestMetrics.fromJson(json['metrics'] as Map<String, dynamic>),
        equityCurve: [
          for (final e in json['equity_curve'] as List)
            EquityPoint.fromJson(e as Map<String, dynamic>),
        ],
        trades: [
          for (final t in json['trades'] as List)
            BacktestTrade.fromJson(t as Map<String, dynamic>),
        ],
      );
}

class OptimizationEntry {
  const OptimizationEntry({
    required this.rank,
    required this.params,
    required this.metrics,
  });

  final int rank;
  final Map<String, dynamic> params;
  final BacktestMetrics metrics;

  factory OptimizationEntry.fromJson(Map<String, dynamic> json) => OptimizationEntry(
        rank: (json['rank'] as num).toInt(),
        params: (json['params'] as Map<String, dynamic>?) ?? const {},
        metrics: BacktestMetrics.fromJson(json['metrics'] as Map<String, dynamic>),
      );
}

class OptimizationResult {
  const OptimizationResult({
    required this.id,
    required this.strategy,
    required this.symbol,
    required this.timeframe,
    required this.metric,
    required this.combinations,
    required this.overfitScore,
    required this.overfitLabel,
    required this.warnings,
    required this.results,
    required this.best,
  });

  final String id;
  final String strategy;
  final String symbol;
  final String timeframe;
  final String metric;
  final int combinations;
  final double overfitScore;
  final String overfitLabel;
  final List<String> warnings;
  final List<OptimizationEntry> results;
  final Map<String, dynamic> best;

  factory OptimizationResult.fromJson(Map<String, dynamic> json) => OptimizationResult(
        id: json['id'] as String,
        strategy: json['strategy'] as String,
        symbol: json['symbol'] as String,
        timeframe: json['timeframe'] as String,
        metric: json['metric'] as String,
        combinations: (json['combinations'] as num).toInt(),
        overfitScore: (json['overfit_score'] as num).toDouble(),
        overfitLabel: json['overfit_label'] as String,
        warnings: [for (final w in json['warnings'] as List) w as String],
        results: [
          for (final e in json['results'] as List)
            OptimizationEntry.fromJson(e as Map<String, dynamic>),
        ],
        best: (json['best'] as Map<String, dynamic>?) ?? const {},
      );
}

/// Renders a parameter value list / range in a compact label.
String describeParams(Map<String, dynamic> params) {
  return params.entries.map((e) => '${e.key}=${e.value}').join('  ');
}
