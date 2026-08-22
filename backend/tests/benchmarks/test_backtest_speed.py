"""Backtest speed benchmarks — bar-by-bar replay throughput."""

from __future__ import annotations

import time

from app.services.backtest import BacktestConfig, run_backtest


def _bench(label: str, func, *, rounds: int = 3) -> float:
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        func()
        times.append(time.perf_counter() - t0)
    avg = sum(times) / len(times)
    print(f"  {label}: {avg:.3f}s avg ({rounds} runs)")
    return avg


def test_backtest_500_bars() -> None:
    config = BacktestConfig(symbol="EURUSD", timeframe="H1", candle_count=500)
    _bench("500 bars  sma_cross", lambda: run_backtest(
        strategy_name="sma_cross", symbol="EURUSD", timeframe="H1",
        params={"fast_period": 10, "slow_period": 30}, config=config,
    ))


def test_backtest_1000_bars() -> None:
    config = BacktestConfig(symbol="EURUSD", timeframe="H1", candle_count=1000)
    _bench("1000 bars sma_cross", lambda: run_backtest(
        strategy_name="sma_cross", symbol="EURUSD", timeframe="H1",
        params={"fast_period": 10, "slow_period": 30}, config=config,
    ))


def test_backtest_2000_bars() -> None:
    config = BacktestConfig(symbol="EURUSD", timeframe="H1", candle_count=2000)
    _bench("2000 bars sma_cross", lambda: run_backtest(
        strategy_name="sma_cross", symbol="EURUSD", timeframe="H1",
        params={"fast_period": 10, "slow_period": 30}, config=config,
    ))


def test_backtest_5000_bars() -> None:
    config = BacktestConfig(symbol="EURUSD", timeframe="H1", candle_count=5000)
    _bench("5000 bars sma_cross", lambda: run_backtest(
        strategy_name="sma_cross", symbol="EURUSD", timeframe="H1",
        params={"fast_period": 10, "slow_period": 30}, config=config,
    ))


def test_backtest_commission_impact() -> None:
    config_low = BacktestConfig(symbol="EURUSD", candle_count=1000, commission_bps=1.0)
    config_high = BacktestConfig(symbol="EURUSD", candle_count=1000, commission_bps=10.0)

    r_low = run_backtest(strategy_name="sma_cross", symbol="EURUSD", timeframe="H1", config=config_low)
    r_high = run_backtest(strategy_name="sma_cross", symbol="EURUSD", timeframe="H1", config=config_high)

    assert r_low["metrics"]["total_trades"] == r_high["metrics"]["total_trades"]
    assert r_low["metrics"]["net_profit"] >= r_high["metrics"]["net_profit"]


def test_backtest_slippage_impact() -> None:
    config_0 = BacktestConfig(symbol="EURUSD", candle_count=500, slippage_points=0.0)
    config_5 = BacktestConfig(symbol="EURUSD", candle_count=500, slippage_points=5.0)

    r_0 = run_backtest(strategy_name="sma_cross", symbol="EURUSD", timeframe="H1", config=config_0)
    r_5 = run_backtest(strategy_name="sma_cross", symbol="EURUSD", timeframe="H1", config=config_5)

    assert r_0["metrics"]["net_profit"] >= r_5["metrics"]["net_profit"]
