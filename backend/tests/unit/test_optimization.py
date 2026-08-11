"""Tests for parameter optimization + overfit warnings (Phase 5 line 4)."""

from __future__ import annotations

import pytest
from app.services.optimization import (
    OptimizationConfig,
    compute_overfit_assessment,
    expand_param_grid,
    optimize_strategy,
)


def test_expand_param_grid_cross_product() -> None:
    grid = expand_param_grid(
        {
            "fast": {"values": [5, 10]},
            "slow": {"values": [20, 30, 40]},
            "volume": {"values": [0.1]},
        }
    )
    assert len(grid) == 2 * 3 * 1
    assert {"fast": 5, "slow": 40, "volume": 0.1} in grid
    assert {"fast": 10, "slow": 30, "volume": 0.1} in grid


def test_expand_param_grid_start_step_stop() -> None:
    grid = expand_param_grid({"fast": {"start": 2, "step": 2, "stop": 6}})
    assert grid == [{"fast": 2}, {"fast": 4}, {"fast": 6}]


def test_expand_param_grid_requires_one_range() -> None:
    with pytest.raises(ValueError):
        expand_param_grid({})


def test_expand_param_grid_rejects_oversized_grid() -> None:
    with pytest.raises(ValueError):
        expand_param_grid({"fast": {"values": list(range(100))}, "slow": {"values": list(range(100))}})


def test_optimize_strategy_returns_ranked_results() -> None:
    result = optimize_strategy(
        strategy_name="sma_cross",
        symbol="EURUSD",
        timeframe="H1",
        param_ranges={"fast": {"values": [5, 10]}, "slow": {"values": [20, 30]}},
        metric="net_profit",
        top_n=10,
        config=OptimizationConfig(symbol="EURUSD", candle_count=400, spread_mult=0.0),
    )
    assert result["strategy"] == "sma_cross"
    assert result["combinations"] == 4
    assert result["overfit_label"] in {"low", "moderate", "high"}
    assert 0.0 <= result["overfit_score"] <= 100.0
    assert isinstance(result["warnings"], list)
    assert result["results"], "expected at least the best configuration"
    assert result["results"][0]["rank"] == 1
    assert "params" in result["results"][0]
    assert "net_profit" in result["results"][0]["metrics"]
    # walk-forward robustness must be computed for a run with trades
    assert result["walk_forward"] is not None
    assert set(result["walk_forward"]) == {"first_half", "second_half"}


def test_optimize_sorts_drawdown_ascending() -> None:
    result = optimize_strategy(
        strategy_name="sma_cross",
        symbol="EURUSD",
        timeframe="H1",
        param_ranges={"fast": {"values": [3, 5, 7]}, "slow": {"values": [20, 30]}},
        metric="max_drawdown_pct",
        top_n=6,
        config=OptimizationConfig(symbol="EURUSD", candle_count=400, spread_mult=0.0),
    )
    values = [r["metrics"]["max_drawdown_pct"] for r in result["results"]]
    assert values == sorted(values)


def test_optimize_captures_invalid_combos() -> None:
    result = optimize_strategy(
        strategy_name="sma_cross",
        symbol="EURUSD",
        timeframe="H1",
        param_ranges={
            "fast": {"values": [20]},
            "slow": {"values": [10]},  # fast >= slow -> StrategyError
        },
        metric="net_profit",
        top_n=10,
        config=OptimizationConfig(symbol="EURUSD", candle_count=400, spread_mult=0.0),
    )
    assert result["combinations"] == 1
    assert "error" in result["results"][0]["metrics"]
    assert result["results"][0]["metrics"]["total_trades"] == 0


def test_overfit_assessment_low_score_when_consistent() -> None:
    best = {"params": {}, "metrics": {"total_trades": 50, "profit_factor": 1.8, "max_drawdown_pct": 5.0}}
    score, warnings = compute_overfit_assessment(
        higher_is_better=True,
        best=best,
        values=[10.0, 8.0, 6.0],
        walk_forward={"first_half": {}, "second_half": {}},
        consistent=True,
        walk_notes=[],
    )
    assert score < 25
    assert any("Walk-forward check passed" in w for w in warnings)


def test_overfit_assessment_high_score_when_fragile() -> None:
    best = {"params": {}, "metrics": {"total_trades": 8, "profit_factor": 0.9, "max_drawdown_pct": 60.0}}
    score, warnings = compute_overfit_assessment(
        higher_is_better=True,
        best=best,
        values=[500.0, -2.0, -3.0],
        walk_forward={"first_half": {}, "second_half": {}},
        consistent=False,
        walk_notes=["first half lost 120.00"],
    )
    assert score >= 25
    assert any("Walk-forward check failed" in w for w in warnings)
