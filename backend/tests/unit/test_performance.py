"""Performance regression tests — ensures key operations stay fast."""

from __future__ import annotations

import time

from app.services.indicators import bollinger, macd, rsi, sma
from app.services.market_data import Candle, SimulatedMarketDataProvider
from app.services.market_structure import analyze as analyze_structure
from app.services.risk_engine import RiskEngine
from app.services.smc_objects import analyze_smc


def _candles(n: int = 500) -> list[Candle]:
    provider = SimulatedMarketDataProvider()
    return provider.candles("EURUSD", "H1", n)


def test_indicator_sma_500_candles_under_50ms() -> None:
    candles = _candles(500)
    start = time.perf_counter()
    sma([c.c for c in candles], 20)
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 50, f"SMA took {elapsed:.1f}ms on 500 candles"


def test_indicator_rsi_500_candles_under_50ms() -> None:
    candles = _candles(500)
    start = time.perf_counter()
    rsi(candles, 14)
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 50, f"RSI took {elapsed:.1f}ms on 500 candles"


def test_indicator_macd_500_candles_under_50ms() -> None:
    candles = _candles(500)
    start = time.perf_counter()
    macd(candles, 12, 26, 9)
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 50, f"MACD took {elapsed:.1f}ms on 500 candles"


def test_indicator_bollinger_500_candles_under_50ms() -> None:
    candles = _candles(500)
    start = time.perf_counter()
    bollinger(candles, 20, 2.0)
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 50, f"Bollinger took {elapsed:.1f}ms on 500 candles"


def test_structure_analysis_500_candles_under_200ms() -> None:
    candles = _candles(500)
    start = time.perf_counter()
    analyze_structure(candles)
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 200, f"Structure analysis took {elapsed:.1f}ms on 500 candles"


def test_smc_analysis_500_candles_under_200ms() -> None:
    candles = _candles(500)
    start = time.perf_counter()
    analyze_smc(candles)
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 200, f"SMC analysis took {elapsed:.1f}ms on 500 candles"


def test_risk_engine_calculation_under_10ms() -> None:
    provider = SimulatedMarketDataProvider()
    engine = RiskEngine(provider)
    start = time.perf_counter()
    engine.position_size(symbol="EURUSD", equity=100_000, risk_pct=1, entry=1.10, sl=1.09)
    engine.margin_required(price=1.10, contract_size=100_000, volume=1.0, leverage=100)
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 10, f"Risk engine took {elapsed:.1f}ms"
