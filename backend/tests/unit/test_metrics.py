"""Tests for the performance metrics service (Phase 5 line 3)."""

from __future__ import annotations

import pytest
from app.services.metrics import bars_per_year, compute_metrics, max_drawdown, sharpe_ratio


def trade(pnl: float, i: int = 0) -> dict:
    return {"id": f"t-{i}", "symbol": "EURUSD", "side": "buy", "net_pnl": pnl}


def curve(values: list[float]) -> list[dict]:
    return [{"ts": f"2024-01-01T{i:02d}:00:00Z", "equity": v} for i, v in enumerate(values)]


def test_empty_run_has_zeroed_metrics() -> None:
    metrics = compute_metrics([], [], initial_balance=100_000, timeframe="H1", end_balance=100_000)
    assert metrics["total_trades"] == 0
    assert metrics["win_rate"] == 0.0
    assert metrics["profit_factor"] is None
    assert metrics["expectancy"] == 0.0
    assert metrics["max_drawdown"] == 0.0
    assert metrics["sharpe"] is None


def test_win_rate_and_expectancy_from_pnl() -> None:
    trades = [trade(100.0), trade(-50.0), trade(200.0), trade(0.0)]
    metrics = compute_metrics(
        trades,
        curve([100_000, 100_100, 100_050, 100_250, 100_250]),
        initial_balance=100_000,
        timeframe="H1",
        end_balance=100_250,
    )
    assert metrics["total_trades"] == 4
    assert metrics["winning_trades"] == 2
    assert metrics["losing_trades"] == 1
    assert metrics["breakeven_trades"] == 1
    assert metrics["win_rate"] == pytest.approx(0.5)
    assert metrics["expectancy"] == pytest.approx(62.5)
    assert metrics["net_profit"] == pytest.approx(250.0)


def test_profit_factor_is_gross_ratio() -> None:
    trades = [trade(300.0), trade(-100.0), trade(-50.0)]
    metrics = compute_metrics(
        trades, curve([100_000]), initial_balance=100_000, timeframe="H1", end_balance=100_150
    )
    assert metrics["gross_profit"] == pytest.approx(300.0)
    assert metrics["gross_loss"] == pytest.approx(150.0)
    assert metrics["profit_factor"] == pytest.approx(2.0)


def test_profit_factor_none_without_losing_trades() -> None:
    metrics = compute_metrics(
        [trade(50.0)],
        curve([100_000]),
        initial_balance=100_000,
        timeframe="H1",
        end_balance=100_050,
    )
    assert metrics["profit_factor"] is None


def test_avg_and_largest_win_loss() -> None:
    trades = [trade(100.0), trade(-40.0), trade(300.0), trade(-10.0)]
    metrics = compute_metrics(
        trades, curve([100_000]), initial_balance=100_000, timeframe="H1", end_balance=100_350
    )
    assert metrics["avg_win"] == pytest.approx(200.0)
    assert metrics["avg_loss"] == pytest.approx(25.0)
    assert metrics["largest_win"] == pytest.approx(300.0)
    assert metrics["largest_loss"] == pytest.approx(-40.0)


def test_max_drawdown_from_peak() -> None:
    dd, pct = max_drawdown(curve([100_000, 110_000, 105_000, 104_000, 112_000, 108_000]))
    assert dd == pytest.approx(6_000.0)
    assert pct == pytest.approx(6_000.0 / 110_000.0 * 100.0, abs=1e-4)
    assert max_drawdown([]) == (0.0, 0.0)


def test_sharpe_ratio_annualized_from_returns() -> None:
    points = [100_000, 101_000, 100_500, 102_000, 102_500, 103_000]
    assert sharpe_ratio(curve(points), "H1") == pytest.approx(
        sharpe_ratio(curve(points), "D1") * (bars_per_year("H1") / bars_per_year("D1")) ** 0.5,
        abs=1e-2,
    )
    assert sharpe_ratio([], "H1") is None
    assert sharpe_ratio(curve([100_000, 100_000, 100_000]), "H1") is None


def test_bars_per_year_defaults() -> None:
    assert bars_per_year("H1") == 8_760
    assert bars_per_year("D1") == 365
    assert bars_per_year("m5") == 105_120
    assert bars_per_year("UNKNOWN") == 8_760
