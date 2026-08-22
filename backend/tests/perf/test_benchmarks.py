"""Performance benchmarks for critical code paths."""

from __future__ import annotations

import time

from app.services.metrics import compute_metrics, max_drawdown, sharpe_ratio
from app.services.risk_engine import RiskEngine, RiskLimits
from app.services.market_data import market_data


def test_max_drawdown_performance() -> None:
    curve = [{"equity": 100000 + i * 100 - (i % 50) * 200} for i in range(5000)]
    start = time.perf_counter()
    for _ in range(100):
        max_drawdown(curve)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"max_drawdown too slow: {elapsed:.2f}s for 100 runs on 5000 bars"


def test_sharpe_ratio_performance() -> None:
    curve = [{"equity": 100000 + i * 50 + (i % 10 - 5) * 100} for i in range(5000)]
    start = time.perf_counter()
    for _ in range(100):
        sharpe_ratio(curve, "H1")
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"sharpe_ratio too slow: {elapsed:.2f}s for 100 runs on 5000 bars"


def test_compute_metrics_performance() -> None:
    trades = [
        {"net_pnl": (i % 3 - 1) * 50.0} for i in range(1000)
    ]
    equity = [{"equity": 100000 + i * 10} for i in range(1000)]
    start = time.perf_counter()
    for _ in range(50):
        compute_metrics(
            trades, equity, initial_balance=100000, timeframe="H1", end_balance=110000
        )
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"compute_metrics too slow: {elapsed:.2f}s"


def test_risk_engine_position_sizing_performance() -> None:
    engine = RiskEngine(market_data, RiskLimits())
    start = time.perf_counter()
    for _ in range(1000):
        engine.symbol_info("EURUSD")
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"symbol_info lookup too slow: {elapsed:.2f}s for 1000 calls"
