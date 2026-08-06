"""Trading performance metrics (Phase 5 line 3).

Computes standard strategy statistics from a completed backtest: trade
distribution (win rate, profit factor, expectancy), drawdown (currency and
percent of peak), and a Sharpe ratio annualized from the per-bar equity curve.
"""

from __future__ import annotations

import itertools
import math

BARS_PER_YEAR: dict[str, int] = {
    "M1": 525_600,
    "M5": 105_120,
    "M15": 35_040,
    "M30": 17_520,
    "H1": 8_760,
    "H4": 2_190,
    "D1": 365,
    "W1": 52,
    "MN": 12,
}


def bars_per_year(timeframe: str) -> int:
    return BARS_PER_YEAR.get(timeframe.upper(), 8_760)


def _round(value: float, digits: int) -> float:
    return round(value, digits)


def max_drawdown(curve: list[dict]) -> tuple[float, float]:
    """Return (max_drawdown, max_drawdown_pct) from an equity curve.

    ``max_drawdown`` is the largest peak-to-trough equity decline in currency;
    ``max_drawdown_pct`` is that decline as a percent of the peak that precedes
    it. An empty curve yields (0.0, 0.0).
    """
    peak = -math.inf
    drawdown = 0.0
    pct = 0.0
    for point in curve:
        equity = float(point["equity"])
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = peak - equity
            if dd > drawdown:
                drawdown = dd
                pct = dd / peak * 100.0
    return _round(drawdown, 2), _round(pct, 4)


def sharpe_ratio(curve: list[dict], timeframe: str) -> float | None:
    """Annualized Sharpe from per-bar equity returns, or None when undefined.

    Uses the population-equivalent standard deviation of the per-bar return
    series; flat (zero-variance) curves and curves with fewer than two bars
    return None.
    """
    if len(curve) < 2:
        return None
    returns: list[float] = []
    for prev, cur in itertools.pairwise(curve):
        prev_equity = float(prev["equity"])
        cur_equity = float(cur["equity"])
        if prev_equity > 0:
            returns.append(cur_equity / prev_equity - 1.0)
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    std = math.sqrt(variance)
    if std == 0.0:
        return None
    return _round(mean / std * math.sqrt(bars_per_year(timeframe)), 3)


def compute_metrics(
    trades: list[dict],
    equity_curve: list[dict],
    *,
    initial_balance: float,
    timeframe: str,
    end_balance: float,
) -> dict:
    """Aggregate per-trade and per-bar statistics into a metrics dict."""
    total = len(trades)
    winners = [t for t in trades if t["net_pnl"] > 0]
    losers = [t for t in trades if t["net_pnl"] < 0]
    breakeven = total - len(winners) - len(losers)
    gross_profit = sum(t["net_pnl"] for t in winners)
    gross_loss = abs(sum(t["net_pnl"] for t in losers))

    profit_factor: float | None
    if total == 0 or gross_loss == 0:
        profit_factor = None
    else:
        profit_factor = _round(gross_profit / gross_loss, 4)

    drawdown, drawdown_pct = max_drawdown(equity_curve)

    return {
        "start_balance": _round(initial_balance, 2),
        "end_balance": _round(end_balance, 2),
        "net_profit": _round(end_balance - initial_balance, 2),
        "total_trades": total,
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "breakeven_trades": breakeven,
        "win_rate": _round(len(winners) / total, 4) if total else 0.0,
        "gross_profit": _round(gross_profit, 2),
        "gross_loss": _round(gross_loss, 2),
        "profit_factor": profit_factor,
        "expectancy": _round(sum(t["net_pnl"] for t in trades) / total, 2) if total else 0.0,
        "avg_win": _round(gross_profit / len(winners), 2) if winners else 0.0,
        "avg_loss": _round(gross_loss / len(losers), 2) if losers else 0.0,
        "largest_win": _round(max((t["net_pnl"] for t in winners), default=0.0), 2),
        "largest_loss": _round(min((t["net_pnl"] for t in losers), default=0.0), 2),
        "max_drawdown": drawdown,
        "max_drawdown_pct": drawdown_pct,
        "sharpe": sharpe_ratio(equity_curve, timeframe),
    }
