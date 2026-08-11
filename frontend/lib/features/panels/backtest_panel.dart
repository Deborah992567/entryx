/// Backtest + Optimizer panel (Phase 5 line 4).
///
/// Tab 1 runs a single deterministic backtest and shows its metrics and trade
/// list; the equity curve and entry/exit markers can be overlaid on a chart.
/// Tab 2 grid-searches strategy parameters and ranks every combination, with
/// overfit warnings and a walk-forward check so "best params" are never shown
/// as a proven edge.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app/theme.dart';
import '../backtest/backtest_models.dart';
import '../chart/chart_store_registry.dart';
import '../chart/chart_models.dart';
import '../../core/api_client.dart';
import '../market/market_watch_store.dart';

class BacktestPanel extends StatefulWidget {
  const BacktestPanel({super.key});

  @override
  State<BacktestPanel> createState() => _BacktestPanelState();
}

class _BacktestPanelState extends State<BacktestPanel> {
  int _tab = 0;

  List<StrategyInfo> _strategies = const [];
  String? _strategy;
  String _symbol = 'XAUUSD';
  Timeframe _tf = Timeframe.h1;

  final _candlesCtrl = TextEditingController(text: '1000');
  final _balanceCtrl = TextEditingController(text: '100000');
  final _leverageCtrl = TextEditingController(text: '100');
  final _commissionCtrl = TextEditingController(text: '2.0');
  final _slippageCtrl = TextEditingController(text: '0.0');
  final _spreadCtrl = TextEditingController(text: '1.0');
  bool _swapEnabled = true;
  bool _marginEnabled = true;

  final Map<String, TextEditingController> _paramCtrls = {};
  final Map<String, List<TextEditingController>> _rangeCtrls = {};

  String _metric = 'net_profit';
  final _topNCtrl = TextEditingController(text: '20');

  BacktestResult? _result;
  bool _running = false;
  String _error = '';

  OptimizationResult? _optResult;
  bool _optimizing = false;
  String _optError = '';

  static const List<(String, String)> _metricOptions = [
    ('net_profit', 'Net profit'),
    ('profit_factor', 'Profit factor'),
    ('sharpe', 'Sharpe'),
    ('expectancy', 'Expectancy'),
    ('win_rate', 'Win rate'),
    ('max_drawdown_pct', 'Max drawdown %'),
  ];

  @override
  void initState() {
    super.initState();
    _loadStrategies();
  }

  @override
  void dispose() {
    for (final c in _paramCtrls.values) {
      c.dispose();
    }
    for (final c in _rangeCtrls.values) {
      for (final cc in c) {
        cc.dispose();
      }
    }
    _candlesCtrl.dispose();
    _balanceCtrl.dispose();
    _leverageCtrl.dispose();
    _commissionCtrl.dispose();
    _slippageCtrl.dispose();
    _spreadCtrl.dispose();
    _topNCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadStrategies() async {
    try {
      final api = context.read<ApiClient>();
      final data = await api.get('/strategies') as List<dynamic>;
      final strategies = [
        for (final e in data) StrategyInfo.fromJson(e as Map<String, dynamic>),
      ];
      if (!mounted) return;
      setState(() {
        _strategies = strategies;
        if (strategies.isNotEmpty && _strategy == null) {
          _strategy = strategies.first.name;
          _initParamControllers(strategies.first);
        }
      });
    } catch (_) {
      // strategies stay empty; the form disables the Run button
    }
  }

  void _initParamControllers(StrategyInfo strategy) {
    for (final c in _paramCtrls.values) {
      c.dispose();
    }
    for (final c in _rangeCtrls.values) {
      for (final cc in c) {
        cc.dispose();
      }
    }
    _paramCtrls.clear();
    _rangeCtrls.clear();

    for (final entry in strategy.params.entries) {
      final defaultValue = (entry.value as num).toDouble();
      _paramCtrls[entry.key] = TextEditingController(text: _fmtNum(defaultValue));

      if (_isIntegral(defaultValue)) {
        final v = defaultValue.toInt();
        _rangeCtrls[entry.key] = [
          TextEditingController(text: '${maxOf(1, v - 5)}'),
          TextEditingController(text: '1'),
          TextEditingController(text: '${v + 5}'),
        ];
      } else {
        _rangeCtrls[entry.key] = [
          TextEditingController(text: _fmtNum(defaultValue * 0.5)),
          TextEditingController(text: _fmtNum(defaultValue * 0.25)),
          TextEditingController(text: _fmtNum(defaultValue * 1.5)),
        ];
      }
    }
  }

  static int maxOf(int a, int b) => a > b ? a : b;

  static bool _isIntegral(double value) => value == value.roundToDouble();

  static String _fmtNum(double v) =>
      v == v.roundToDouble() ? v.toInt().toString() : v.toString();

  void _selectStrategy(String name) {
    final strategy = _strategies.firstWhere((s) => s.name == name, orElse: () => _strategies.first);
    setState(() {
      _strategy = name;
      _initParamControllers(strategy);
    });
  }

  double _num(TextEditingController c, double fallback) =>
      double.tryParse(c.text.trim()) ?? fallback;

  Map<String, dynamic> _configBody() => {
        'initial_balance': _num(_balanceCtrl, 100000),
        'leverage': _num(_leverageCtrl, 100).toInt(),
        'commission_bps': _num(_commissionCtrl, 2.0),
        'slippage_points': _num(_slippageCtrl, 0.0),
        'spread_mult': _num(_spreadCtrl, 1.0),
        'swap_enabled': _swapEnabled,
        'margin_enabled': _marginEnabled,
      };

  Map<String, dynamic> _paramsBody() => {
        for (final e in _paramCtrls.entries) e.key: _num(e.value, 0),
      };

  Map<String, dynamic> _rangeBody() => {
        for (final e in _rangeCtrls.entries)
          e.key: {
            'start': _num(e.value[0], 0),
            'step': _num(e.value[1], 1),
            'stop': _num(e.value[2], 1),
          },
      };

  Future<void> _runBacktest() async {
    final strategy = _strategy;
    if (strategy == null) return;
    setState(() {
      _running = true;
      _error = '';
    });
    try {
      final api = context.read<ApiClient>();
      final data = await api.post('/backtests', body: {
        'strategy': strategy,
        'symbol': _symbol,
        'timeframe': _tf.api,
        'candle_count': _num(_candlesCtrl, 1000).toInt(),
        'params': _paramsBody(),
        'config': _configBody(),
      });
      if (!mounted) return;
      setState(() => _result = BacktestResult.fromJson(data as Map<String, dynamic>));
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = 'Backtest failed: $e');
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  Future<void> _runOptimize() async {
    final strategy = _strategy;
    if (strategy == null) return;
    setState(() {
      _optimizing = true;
      _optError = '';
    });
    try {
      final api = context.read<ApiClient>();
      final data = await api.post('/backtests/optimize', body: {
        'strategy': strategy,
        'symbol': _symbol,
        'timeframe': _tf.api,
        'candle_count': _num(_candlesCtrl, 1000).toInt(),
        'metric': _metric,
        'top_n': _num(_topNCtrl, 20).toInt(),
        'param_ranges': _rangeBody(),
        'config': _configBody(),
      });
      if (!mounted) return;
      setState(() => _optResult = OptimizationResult.fromJson(data as Map<String, dynamic>));
    } catch (e) {
      if (!mounted) return;
      setState(() => _optError = 'Optimization failed: $e');
    } finally {
      if (mounted) setState(() => _optimizing = false);
    }
  }

  Future<void> _overlayOnChart(BacktestResult result) async {
    final chart = context.read<ChartStoreRegistry>().firstChart;
    if (chart == null) {
      _showMessage('Add a chart panel first, then overlay the result.');
      return;
    }
    chart.setBacktest(result);
    _showMessage('Overlaid ${result.strategy} ${result.timeframe} on the chart.');
  }

  Future<void> _overlayBest() async {
    final opt = _optResult;
    if (opt == null) return;
    final best = opt.best;
    final params = ((best['params'] as Map?) ?? const {}).cast<String, dynamic>();
    setState(() {
      _running = true;
      _error = '';
    });
    try {
      final api = context.read<ApiClient>();
      final data = await api.post('/backtests', body: {
        'strategy': opt.strategy,
        'symbol': opt.symbol,
        'timeframe': opt.timeframe,
        'candle_count': _num(_candlesCtrl, 1000).toInt(),
        'params': params,
        'config': _configBody(),
      });
      if (!mounted) return;
      final result = BacktestResult.fromJson(data as Map<String, dynamic>);
      setState(() => _result = result);
      await _overlayOnChart(result);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = 'Backtest failed: $e');
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(
        content: Text(message, style: const TextStyle(fontSize: 12)),
        duration: const Duration(seconds: 2),
        backgroundColor: EntryXColors.bgRaised,
      ));
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          height: 30,
          child: Row(
            children: [
              _TabChip(
                label: 'Backtest',
                icon: Icons.science_outlined,
                selected: _tab == 0,
                onTap: () => setState(() => _tab = 0),
              ),
              _TabChip(
                label: 'Optimizer',
                icon: Icons.tune,
                selected: _tab == 1,
                onTap: () => setState(() => _tab = 1),
              ),
              const Spacer(),
              if (_result != null)
                TextButton.icon(
                  onPressed: () => _overlayOnChart(_result!),
                  icon: const Icon(Icons.query_stats, size: 14),
                  label: const Text('Overlay on chart', style: TextStyle(fontSize: 11)),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    foregroundColor: EntryXColors.accentBright,
                  ),
                ),
              if (_result != null)
                IconButton(
                  onPressed: () {
                    context.read<ChartStoreRegistry>().firstChart?.clearBacktest();
                    setState(() => _result = null);
                  },
                  icon: const Icon(Icons.close, size: 14, color: EntryXColors.textDim),
                  tooltip: 'Clear result and overlay',
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
                ),
              const SizedBox(width: 4),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(child: _tab == 0 ? _buildBacktestTab() : _buildOptimizerTab()),
      ],
    );
  }

  // ------------------------------------------------------------------ forms

  Widget _buildBacktestTab() {
    return _FormScaffold(
      running: _running,
      error: _error,
      onRun: _runBacktest,
      runLabel: 'Run backtest',
      children: [
        _baseForm(showParams: true),
        if (_result != null) ...[
          _SectionTitle('Results · ${_result!.strategy} ${_result!.timeframe}'),
          _metricsGrid(_result!.metrics),
          const SizedBox(height: 8),
          _TradesTable(trades: _result!.trades),
        ],
      ],
    );
  }

  Widget _buildOptimizerTab() {
    return _FormScaffold(
      running: _optimizing,
      error: _optError,
      onRun: _runOptimize,
      runLabel: 'Optimize',
      children: [
        _baseForm(showParams: false),
        _SectionTitle('Optimization target'),
        _row(
          children: [
            _label('Metric', width: 64),
            Expanded(
              child: _Dropdown<String>(
                value: _metric,
                items: [
                  for (final (value, label) in _metricOptions)
                    (value, label, null),
                ],
                onChanged: (v) => setState(() => _metric = v!),
              ),
            ),
            const SizedBox(width: 8),
            _label('Top N', width: 44),
            SizedBox(width: 70, child: _field(_topNCtrl)),
          ],
        ),
        const SizedBox(height: 8),
        _SectionTitle('Parameter ranges'),
        Padding(
          padding: const EdgeInsets.only(bottom: 4, left: 64),
          child: Row(
            children: [
              _label('start', width: 64),
              const SizedBox(width: 6),
              _label('step', width: 64),
              const SizedBox(width: 6),
              _label('stop', width: 64),
            ],
          ),
        ),
        for (final entry in _rangeCtrls.entries)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: _row(
              children: [
                _label(entry.key, width: 64),
                for (var i = 0; i < 3; i++) ...[
                  SizedBox(width: 64, child: _field(entry.value[i])),
                  const SizedBox(width: 6),
                ],
              ],
            ),
          ),
        if (_optResult != null) ...[
          const SizedBox(height: 4),
          _OptResultView(
            result: _optResult!,
            onOverlayBest: _overlayBest,
          ),
        ],
      ],
    );
  }

  Widget _baseForm({required bool showParams}) {
    final watch = context.watch<MarketWatchStore>();
    final symbols = watch.symbols.map((s) => s.symbol).toList();
    final strategyNames = [for (final s in _strategies) s.name];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionTitle('Strategy'),
        _row(
          children: [
            _label('Strategy', width: 64),
            Expanded(
              child: _Dropdown<String>(
                value: _strategy,
                items: [
                  for (final name in strategyNames) (name, name, null),
                ],
                onChanged: (v) => v == null ? null : _selectStrategy(v),
                hint: _strategies.isEmpty ? 'No strategies loaded' : 'Select…',
              ),
            ),
            const SizedBox(width: 8),
            _label('Symbol', width: 44),
            Expanded(
              child: _Dropdown<String>(
                value: symbols.contains(_symbol) ? _symbol : null,
                items: [
                  for (final s in symbols) (s, s, null),
                ],
                onChanged: (v) => v == null ? null : setState(() => _symbol = v),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        _row(
          children: [
            _label('Timeframe', width: 64),
            Expanded(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    for (final tf in Timeframe.values)
                      Padding(
                        padding: const EdgeInsets.only(right: 4),
                        child: ChoiceChip(
                          label: Text(tf.api,
                              style: const TextStyle(fontSize: 10)),
                          selected: _tf == tf,
                          onSelected: (_) => setState(() => _tf = tf),
                          visualDensity: VisualDensity.compact,
                          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          backgroundColor: EntryXColors.bgRaised,
                          selectedColor: EntryXColors.accentBright,
                          side: const BorderSide(color: EntryXColors.border, width: 0.5),
                          showCheckmark: false,
                          padding: const EdgeInsets.symmetric(horizontal: 6),
                        ),
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 8),
            _label('Bars', width: 30),
            SizedBox(width: 70, child: _field(_candlesCtrl)),
          ],
        ),
        const SizedBox(height: 8),
        if (showParams && _paramCtrls.isNotEmpty) ...[
          _SectionTitle('Parameters'),
          for (final entry in _paramCtrls.entries)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: _row(
                children: [
                  _label(entry.key, width: 64),
                  SizedBox(width: 90, child: _field(entry.value)),
                ],
              ),
            ),
        ],
        _SectionTitle('Execution config'),
        _row(
          children: [
            _label('Balance', width: 64),
            SizedBox(width: 90, child: _field(_balanceCtrl)),
            const SizedBox(width: 8),
            _label('Leverage', width: 56),
            SizedBox(width: 70, child: _field(_leverageCtrl)),
          ],
        ),
        const SizedBox(height: 6),
        _row(
          children: [
            _label('Comm bps', width: 64),
            SizedBox(width: 90, child: _field(_commissionCtrl)),
            const SizedBox(width: 8),
            _label('Slippage', width: 56),
            SizedBox(width: 70, child: _field(_slippageCtrl)),
          ],
        ),
        const SizedBox(height: 6),
        _row(
          children: [
            _label('Spread ×', width: 64),
            SizedBox(width: 90, child: _field(_spreadCtrl)),
            const SizedBox(width: 12),
            FilterChip(
              label: const Text('Swap', style: TextStyle(fontSize: 10)),
              selected: _swapEnabled,
              onSelected: (v) => setState(() => _swapEnabled = v),
              visualDensity: VisualDensity.compact,
              backgroundColor: EntryXColors.bgRaised,
              selectedColor: EntryXColors.accentBright,
              side: const BorderSide(color: EntryXColors.border, width: 0.5),
            ),
            const SizedBox(width: 6),
            FilterChip(
              label: const Text('Margin', style: TextStyle(fontSize: 10)),
              selected: _marginEnabled,
              onSelected: (v) => setState(() => _marginEnabled = v),
              visualDensity: VisualDensity.compact,
              backgroundColor: EntryXColors.bgRaised,
              selectedColor: EntryXColors.accentBright,
              side: const BorderSide(color: EntryXColors.border, width: 0.5),
            ),
          ],
        ),
        const SizedBox(height: 10),
        const Divider(height: 1),
        const SizedBox(height: 8),
      ],
    );
  }

  Widget _metricsGrid(BacktestMetrics m) {
    final pnlColor = m.netProfit >= 0 ? EntryXColors.up : EntryXColors.down;
    final pf = m.profitFactor;
    final sharpe = m.sharpe;
    final metrics = <String, (String, Color?)>{
      'Net profit': (fmtMoney(m.netProfit), pnlColor),
      'End balance': (fmtMoney(m.endBalance), null),
      'Return': (m.startBalance > 0
          ? '${(m.netProfit / m.startBalance * 100).toStringAsFixed(2)}%'
          : '--', pnlColor),
      'Total trades': ('${m.totalTrades}', null),
      'Win rate': ('${(m.winRate * 100).toStringAsFixed(1)}%', null),
      'Profit factor': (pf == null ? '--' : pf.toStringAsFixed(2), pf != null && pf >= 1 ? EntryXColors.up : EntryXColors.down),
      'Expectancy': (fmtMoney(m.expectancy), m.expectancy >= 0 ? EntryXColors.up : EntryXColors.down),
      'Max drawdown': (fmtMoney(m.maxDrawdown), EntryXColors.down),
      'Max DD %': ('${m.maxDrawdownPct.toStringAsFixed(2)}%', EntryXColors.down),
      'Sharpe': (sharpe == null ? '--' : sharpe.toStringAsFixed(2), null),
      'Gross profit': (fmtMoney(m.grossProfit), EntryXColors.up),
      'Gross loss': (fmtMoney(m.grossLoss), EntryXColors.down),
    };
    return GridView.count(
      crossAxisCount: 4,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      childAspectRatio: 2.6,
      children: [
        for (final entry in metrics.entries)
          Container(
            margin: const EdgeInsets.all(3),
            padding: const EdgeInsets.symmetric(horizontal: 8),
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
                    style: const TextStyle(fontSize: 9, color: EntryXColors.textDim)),
                const SizedBox(height: 2),
                Text(
                  entry.value.$1,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: entry.value.$2 ?? EntryXColors.text,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _label(String text, {required double width}) {
    return SizedBox(
      width: width,
      child: Text(
        text,
        style: TextStyle(
          fontSize: 10,
          color: EntryXColors.textDim,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  Widget _row({required List<Widget> children}) {
    return Row(crossAxisAlignment: CrossAxisAlignment.center, children: children);
  }

  Widget _field(TextEditingController controller) {
    return TextField(
      controller: controller,
      style: const TextStyle(fontSize: 11),
      keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
      decoration: const InputDecoration(
        contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 6),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Optimizer result view
// ---------------------------------------------------------------------------

class _OptResultView extends StatelessWidget {
  const _OptResultView({required this.result, required this.onOverlayBest});

  final OptimizationResult result;
  final VoidCallback onOverlayBest;

  @override
  Widget build(BuildContext context) {
    final label = result.overfitLabel;
    final scoreColor = switch (label) {
      'low' => EntryXColors.up,
      'moderate' => EntryXColors.warn,
      _ => EntryXColors.down,
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Divider(height: 1),
        const SizedBox(height: 6),
        _SectionTitle('Optimization results'),
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: scoreColor.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: scoreColor.withValues(alpha: 0.5)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    'Overfit risk: ${result.overfitScore.toStringAsFixed(0)}/100 ($label)',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: scoreColor,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    '${result.combinations} combinations on ${result.metric}',
                    style: const TextStyle(fontSize: 10, color: EntryXColors.textDim),
                  ),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: onOverlayBest,
                    icon: const Icon(Icons.query_stats, size: 14),
                    label: const Text('Backtest & overlay best', style: TextStyle(fontSize: 11)),
                    style: TextButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                      foregroundColor: EntryXColors.accentBright,
                    ),
                  ),
                ],
              ),
              if (result.warnings.isNotEmpty) ...[
                const SizedBox(height: 6),
                for (final w in result.warnings)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 2),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.warning_amber_rounded,
                            size: 12, color: EntryXColors.warn),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(w,
                              style: const TextStyle(
                                  fontSize: 10, color: EntryXColors.text)),
                        ),
                      ],
                    ),
                  ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 8),
        const Row(
          children: [
            _OptCol('#', 30), _OptCol('Params', 120), _OptCol('Net', 80, alignEnd: true),
            _OptCol('PF', 56, alignEnd: true), _OptCol('Trades', 56, alignEnd: true),
            _OptCol('DD %', 64, alignEnd: true),
          ],
        ),
        const Divider(height: 1),
        for (final entry in result.results) ...[
          Row(
            children: [
              _cell('${entry.rank}', width: 30),
              _cell(describeParams(entry.params), width: 120, dim: true),
              _cell(fmtMoney(entry.metrics.netProfit),
                  width: 80, color: entry.metrics.netProfit >= 0 ? EntryXColors.up : EntryXColors.down, alignEnd: true),
              _cell(entry.metrics.profitFactor == null
                  ? '--'
                  : entry.metrics.profitFactor!.toStringAsFixed(2), width: 56, alignEnd: true),
              _cell('${entry.metrics.totalTrades}', width: 56, alignEnd: true),
              _cell('${entry.metrics.maxDrawdownPct.toStringAsFixed(1)}%', width: 64, alignEnd: true),
            ],
          ),
          const Divider(height: 1),
        ],
      ],
    );
  }
}

class _OptCol extends StatelessWidget {
  const _OptCol(this.text, this.width, {this.alignEnd = false});
  final String text;
  final double width;
  final bool alignEnd;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
        child: Text(
          text,
          textAlign: alignEnd ? TextAlign.end : TextAlign.start,
          style: const TextStyle(fontSize: 9, color: EntryXColors.textDim),
        ),
      ),
    );
  }
}

Widget _cell(String text,
    {required double width, Color? color, bool alignEnd = false, bool dim = false}) {
  return SizedBox(
    width: width,
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
      child: Text(
        text,
        textAlign: alignEnd ? TextAlign.end : TextAlign.start,
        style: TextStyle(
          fontSize: 10,
          color: dim ? EntryXColors.textDim : (color ?? EntryXColors.text),
        ),
        overflow: TextOverflow.ellipsis,
      ),
    ),
  );
}

// ---------------------------------------------------------------------------
// Trades table
// ---------------------------------------------------------------------------

class _TradesTable extends StatelessWidget {
  const _TradesTable({required this.trades});

  final List<BacktestTrade> trades;

  @override
  Widget build(BuildContext context) {
    if (trades.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(8),
        child: Text('No trades were generated.',
            style: TextStyle(fontSize: 11, color: EntryXColors.textDim)),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionTitle('Trades'),
        const Row(
          children: [
            _TradeCol('Side', 40), _TradeCol('Vol', 46), _TradeCol('Open', 74),
            _TradeCol('Close', 74), _TradeCol('Net P&L', 80, alignEnd: true),
            _TradeCol('Comm', 60, alignEnd: true), _TradeCol('Swap', 54, alignEnd: true),
          ],
        ),
        const Divider(height: 1),
        for (final t in trades) ...[
          Row(
            children: [
              _cell(t.side.toUpperCase(), width: 40,
                  color: t.side == 'buy' ? EntryXColors.up : EntryXColors.down),
              _cell(fmtVol(t.volume), width: 46),
              _cell(fmtPrice(t.openPrice), width: 74),
              _cell(fmtPrice(t.closePrice), width: 74),
              _cell(fmtMoney(t.netPnl), width: 80,
                  color: t.netPnl >= 0 ? EntryXColors.up : EntryXColors.down, alignEnd: true),
              _cell(fmtMoney(t.commission), width: 60, alignEnd: true),
              _cell(fmtMoney(t.swap), width: 54, alignEnd: true),
            ],
          ),
          const Divider(height: 1),
        ],
      ],
    );
  }
}

class _TradeCol extends StatelessWidget {
  const _TradeCol(this.text, this.width, {this.alignEnd = false});
  final String text;
  final double width;
  final bool alignEnd;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
        child: Text(
          text,
          textAlign: alignEnd ? TextAlign.end : TextAlign.start,
          style: const TextStyle(fontSize: 9, color: EntryXColors.textDim),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Shared bits
// ---------------------------------------------------------------------------

class _FormScaffold extends StatelessWidget {
  const _FormScaffold({
    required this.running,
    required this.error,
    required this.onRun,
    required this.runLabel,
    required this.children,
  });

  final bool running;
  final String error;
  final VoidCallback onRun;
  final String runLabel;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ...children,
                const SizedBox(height: 6),
              ],
            ),
          ),
        ),
        const Divider(height: 1),
        Container(
          height: 38,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          child: Row(
            children: [
              if (error.isNotEmpty) ...[
                Icon(Icons.error_outline, size: 13, color: EntryXColors.down),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(error,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 10, color: EntryXColors.down)),
                ),
                const SizedBox(width: 8),
              ],
              const Spacer(),
              FilledButton.icon(
                onPressed: running ? null : onRun,
                icon: running
                    ? const SizedBox(
                        width: 12,
                        height: 12,
                        child: CircularProgressIndicator(strokeWidth: 1.5),
                      )
                    : const Icon(Icons.play_arrow, size: 14),
                label: Text(runLabel, style: const TextStyle(fontSize: 11)),
                style: FilledButton.styleFrom(
                  backgroundColor: EntryXColors.accent,
                  foregroundColor: const Color(0xFF0E1116),
                  visualDensity: VisualDensity.compact,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 2, bottom: 6),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.5,
          color: EntryXColors.accentBright,
        ),
      ),
    );
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
          border: Border.all(color: selected ? EntryXColors.accent : EntryXColors.border),
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

class _Dropdown<T> extends StatelessWidget {
  const _Dropdown({
    required this.value,
    required this.items,
    required this.onChanged,
    this.hint,
  });

  final T? value;
  final List<(T, String, Color?)> items;
  final ValueChanged<T?> onChanged;
  final String? hint;

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<T>(
      initialValue: value,
      isDense: true,
      items: [
        for (final (v, label, color) in items)
          DropdownMenuItem(
            value: v,
            child: Text(label,
                style: TextStyle(
                    fontSize: 11, color: color ?? EntryXColors.text)),
          ),
      ],
      onChanged: onChanged,
      hint: Text(hint ?? '', style: const TextStyle(fontSize: 11, color: EntryXColors.textDim)),
      style: const TextStyle(fontSize: 11, color: EntryXColors.text),
      decoration: const InputDecoration(
        contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      ),
      dropdownColor: EntryXColors.bgRaised,
    );
  }
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
