"""Parameter optimization with overfit warnings (Phase 5 line 4).

Runs a deterministic grid search over strategy parameters using the same
backtester as a single run, ranks every combination by a chosen metric, and
flags configurations that are likely overfit to the sample:

- too few trades for the result to be meaningful;
- a weak/absent edge in the best configuration (low profit factor);
- an extreme drawdown that makes the equity path fragile;
- a best-vs-median performance outlier (a lone spike in the parameter
  surface is a classic overfit signature);
- walk-forward failure: the best configuration is replayed on the first and
  second halves of the same series and must be profitable in both for the
  edge to look real.

The output is a ranked table of the top configurations plus an aggregate
``overfit_score`` (0–100) and a human-readable label so the user is never
shown a "best" parameter set as if it were a proven edge.
"""

from __future__ import annotations

import itertools
import math
import statistics
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.backtest import BacktestConfig, run_backtest
from app.services.market_data import Candle, MarketDataProvider, market_data
from app.services.strategy import _REGISTRY

# Metrics that are "lower is better" (typically drawdown-related).
DESCENDING_METRICS = {"max_drawdown", "max_drawdown_pct", "avg_loss", "largest_loss"}
MAX_COMBINATIONS = 500
MIN_TRADES_THRESHOLD = 20
PROFIT_FACTOR_THRESHOLD = 1.2
DRAWDOWN_THRESHOLD_PCT = 30.0


@dataclass(frozen=True)
class OptimizationConfig:
    symbol: str
    timeframe: str = "H1"
    candle_count: int = 1000
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    initial_balance: float = 100_000.0
    leverage: int = 100
    commission_bps: float = 2.0
    slippage_points: float = 0.0
    spread_mult: float = 1.0
    swap_enabled: bool = True
    margin_enabled: bool = True


def expand_param_grid(ranges: dict[str, dict]) -> list[dict]:
    """Cross-product of every parameter's value list.

    Each range must be either ``{"values": [...]}`` or
    ``{"start": ..., "step": ..., "stop": ...}``. Values are kept in the
    order given so callers can present a stable table.
    """
    if not ranges:
        raise ValueError("at least one parameter range is required")
    keys = list(ranges)
    pools: list[list[object]] = []
    for key in keys:
        spec = ranges[key]
        if not isinstance(spec, dict):
            raise ValueError(f"param range for '{key}' must be a dict")
        if "values" in spec:
            values = list(spec["values"])
        elif "start" in spec and "step" in spec and "stop" in spec:
            values = _arange(float(spec["start"]), float(spec["step"]), float(spec["stop"]))
        else:
            raise ValueError(f"param range for '{key}' must define 'values' or start/step/stop")
        if not values:
            raise ValueError(f"empty range for param '{key}'")
        pools.append(values)
    combos = list(itertools.product(*pools))
    if len(combos) > MAX_COMBINATIONS:
        raise ValueError(f"grid would run {len(combos)} combinations (max {MAX_COMBINATIONS})")
    return [dict(zip(keys, combo, strict=True)) for combo in combos]


def _arange(start: float, step: float, stop: float) -> list[float]:
    values: list[float] = []
    value = start
    guard = 0
    while (step > 0 and value <= stop) or (step < 0 and value >= stop):
        values.append(round(value, 10))
        value += step
        guard += 1
        if guard > 10_000:
            break
    return values


def _metric_value(metrics: dict, metric: str) -> float | None:
    value = metrics.get(metric)
    if value is None:
        return None
    return float(value)


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _walk_forward_robustness(
    strategy_name: str,
    symbol: str,
    timeframe: str,
    params: dict,
    config: OptimizationConfig,
    candles: list[Candle],
) -> tuple[dict, bool, list[str]]:
    """Replay the best params on each half of the series; return results and consistency."""
    mid = len(candles) // 2
    if mid < 2:
        return {}, False, ["series too short for a walk-forward split"]
    first = run_backtest(
        strategy_name=strategy_name,
        symbol=symbol,
        timeframe=timeframe,
        params=params,
        candles=candles[:mid],
        config=BacktestConfig(
            symbol=symbol,
            timeframe=timeframe,
            initial_balance=config.initial_balance,
            leverage=config.leverage,
            commission_bps=config.commission_bps,
            slippage_points=config.slippage_points,
            spread_mult=config.spread_mult,
            swap_enabled=config.swap_enabled,
            margin_enabled=config.margin_enabled,
        ),
    )
    second = run_backtest(
        strategy_name=strategy_name,
        symbol=symbol,
        timeframe=timeframe,
        params=params,
        candles=candles[mid:],
        config=BacktestConfig(
            symbol=symbol,
            timeframe=timeframe,
            initial_balance=config.initial_balance,
            leverage=config.leverage,
            commission_bps=config.commission_bps,
            slippage_points=config.slippage_points,
            spread_mult=config.spread_mult,
            swap_enabled=config.swap_enabled,
            margin_enabled=config.margin_enabled,
        ),
    )
    halves = {"first_half": first["metrics"], "second_half": second["metrics"]}
    notes: list[str] = []
    profitable = 0
    for label, run in (("first", first), ("second", second)):
        net = run["metrics"]["net_profit"]
        trades = run["metrics"]["total_trades"]
        if trades < MIN_TRADES_THRESHOLD:
            notes.append(f"{label} half only had {trades} trades")
        elif net > 0:
            profitable += 1
        else:
            notes.append(f"{label} half lost {abs(net):.2f}")
    consistent = profitable == 2 and not notes
    if not consistent:
        notes.append("best params were not profitable in both halves of the sample")
    return halves, consistent, notes


def compute_overfit_assessment(
    *,
    higher_is_better: bool,
    best: dict,
    values: list[float],
    walk_forward: dict | None,
    consistent: bool,
    walk_notes: list[str],
) -> tuple[float, list[str]]:
    """Return (overfit_score, warnings) from the ranked results and walk-forward check.

    ``best`` is the top-ranked entry (``{"params", "metrics"}``), ``values`` are
    the metric values across every combination, and ``walk_forward``/``consistent``
    come from the robustness replay. The score is a 0–100 heuristic: higher means
    the top configuration is more likely to be noise.
    """
    score = 0.0
    warnings: list[str] = []
    best_metrics = best["metrics"]

    trades = int(best_metrics.get("total_trades", 0))
    if trades < MIN_TRADES_THRESHOLD:
        score += 25
        warnings.append(
            f"Only {trades} trades — the result is too small a sample to trust "
            f"(need at least {MIN_TRADES_THRESHOLD})."
        )

    pf = best_metrics.get("profit_factor")
    if pf is not None and pf < PROFIT_FACTOR_THRESHOLD:
        score += 20
        warnings.append(
            f"Best profit factor {pf:.2f} is below {PROFIT_FACTOR_THRESHOLD} — the edge is weak."
        )

    dd_pct = best_metrics.get("max_drawdown_pct", 0.0)
    if dd_pct is not None and dd_pct > DRAWDOWN_THRESHOLD_PCT:
        score += 15
        warnings.append(f"Best configuration drawdown {dd_pct:.1f}% is very high.")

    median = _median(values)
    if median is None:
        score += 15
        warnings.append(
            "No comparable metric values across the grid — the best result cannot be "
            "benchmarked against its neighbors."
        )
    elif higher_is_better and values:
        best_value = values[0]
        if median <= 0:
            score += 15
            warnings.append(
                "The median configuration is not profitable — the best result is likely "
                "a lucky point on the parameter surface."
            )
        else:
            ratio = best_value / median
            if ratio >= 2.0:
                score += 25
                warnings.append(
                    f"Best result is {ratio:.1f}× the median ({median:.2f}) — a lone "
                    "performance spike that usually signals overfitting."
                )

    if walk_forward is not None:
        if consistent:
            warnings.append(
                "Walk-forward check passed: the best params were profitable in both halves."
            )
        else:
            score += 30
            warnings.append("Walk-forward check failed: " + "; ".join(walk_notes) + ".")

    score = min(100.0, score)
    return score, warnings


def optimize_strategy(
    *,
    strategy_name: str,
    symbol: str,
    timeframe: str,
    param_ranges: dict[str, dict],
    metric: str = "net_profit",
    top_n: int = 20,
    config: OptimizationConfig | None = None,
    provider: MarketDataProvider | None = None,
) -> dict:
    """Grid-search ``param_ranges`` and return a ranked table plus overfit warnings."""
    config = config or OptimizationConfig(symbol=symbol, timeframe=timeframe)
    provider = provider or market_data
    higher_is_better = metric not in DESCENDING_METRICS
    if strategy_name not in _REGISTRY:
        raise KeyError(f"unknown strategy: {strategy_name}")
    combos = expand_param_grid(param_ranges)

    candles = provider.candles(symbol, timeframe, config.candle_count, config.end_ts)
    if config.start_ts is not None:
        candles = [c for c in candles if c.ts >= config.start_ts]
    if not candles:
        raise ValueError("no candles to optimize over")

    strategy_class_name = strategy_name
    results: list[dict] = []
    for combo in combos:
        try:
            run = run_backtest(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                params=combo,
                candles=candles,
                config=BacktestConfig(
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_count=config.candle_count,
                    initial_balance=config.initial_balance,
                    leverage=config.leverage,
                    commission_bps=config.commission_bps,
                    slippage_points=config.slippage_points,
                    spread_mult=config.spread_mult,
                    swap_enabled=config.swap_enabled,
                    margin_enabled=config.margin_enabled,
                ),
            )
        except Exception as exc:  # a bad combo must not kill the whole grid
            results.append(
                {
                    "params": combo,
                    "metrics": {
                        "start_balance": config.initial_balance,
                        "end_balance": config.initial_balance,
                        "net_profit": 0.0,
                        "total_trades": 0,
                        "win_rate": 0.0,
                        "profit_factor": None,
                        "max_drawdown_pct": 0.0,
                        "error": f"{exc.__class__.__name__}: {exc}",
                    },
                }
            )
            continue
        results.append({"params": combo, "metrics": run["metrics"]})

    reverse = metric not in DESCENDING_METRICS

    def sort_key(entry: dict) -> float:
        value = _metric_value(entry["metrics"], metric)
        if value is None:
            return -math.inf
        return value

    results.sort(key=sort_key, reverse=reverse)

    values = [v for v in (_metric_value(r["metrics"], metric) for r in results) if v is not None]
    best = results[0] if results else {"params": {}, "metrics": {}}

    walk_forward: dict | None = None
    consistent = False
    walk_notes: list[str] = []
    if best.get("metrics", {}).get("total_trades", 0) > 0:
        walk_forward, consistent, walk_notes = _walk_forward_robustness(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            params=best["params"],
            config=config,
            candles=candles,
        )

    overfit_score, warnings = compute_overfit_assessment(
        higher_is_better=higher_is_better,
        best=best,
        values=values,
        walk_forward=walk_forward,
        consistent=consistent,
        walk_notes=walk_notes,
    )

    label = "low" if overfit_score < 25 else ("moderate" if overfit_score < 50 else "high")

    table: list[dict] = []
    for rank, entry in enumerate(results[:top_n], start=1):
        table.append(
            {
                "rank": rank,
                "params": entry["params"],
                "metrics": entry["metrics"],
            }
        )

    return {
        "id": f"opt-{uuid.uuid4().hex[:12]}",
        "strategy": strategy_class_name,
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "candle_count": len(candles),
        "metric": metric,
        "top_n": top_n,
        "combinations": len(results),
        "started_at": datetime.now(UTC),
        "finished_at": datetime.now(UTC),
        "config": {
            "initial_balance": config.initial_balance,
            "leverage": config.leverage,
            "commission_bps": config.commission_bps,
            "slippage_points": config.slippage_points,
            "spread_mult": config.spread_mult,
            "swap_enabled": config.swap_enabled,
            "margin_enabled": config.margin_enabled,
        },
        "overfit_score": round(overfit_score, 1),
        "overfit_label": label,
        "warnings": warnings,
        "walk_forward": walk_forward,
        "best": {
            "params": best["params"],
            "metrics": best["metrics"],
            "run_id": None,
        },
        "results": table,
    }


class OptimizationStore:
    """In-memory, per-user store of completed optimization runs."""

    def __init__(self) -> None:
        self._runs: dict[str, tuple[int, dict]] = {}
        self._lock = threading.Lock()

    def save(self, user_id: int, result: dict) -> dict:
        with self._lock:
            self._runs[result["id"]] = (user_id, result)
        return result

    def get(self, user_id: int, run_id: str) -> dict:
        with self._lock:
            entry = self._runs.get(run_id)
        if entry is None or entry[0] != user_id:
            raise KeyError(run_id)
        return entry[1]

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()


optimization_store = OptimizationStore()
