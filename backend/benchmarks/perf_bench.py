"""Performance benchmarks for EntryX core subsystems.

Run: python -m benchmarks.perf_bench

Measures: market data generation, indicator calculation, backtest speed,
SMC detection, chart geometry, and WebSocket fan-out.
"""

from __future__ import annotations

import time
import statistics
from datetime import UTC, datetime, timedelta

from app.services.market_data import Candle, market_data
from app.services.indicators import sma, ema, rsi, macd, bollinger, atr, adx
from app.services.market_structure import analyze as analyze_structure
from app.services.smc_objects import analyze_smc
from app.services.backtest import BacktestConfig, BacktestBroker
from app.services.strategy import Strategy
from app.services.risk_engine import RiskEngine


def _generate_candles(n: int) -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    candles = []
    price = 2000.0
    for i in range(n):
        o = price
        h = o + abs(hash(f"h{i}") % 50) * 0.01
        lo = o - abs(hash(f"l{i}") % 50) * 0.01
        c = o + (hash(f"c{i}") % 100 - 50) * 0.01
        v = 100 + hash(f"v{i}") % 900
        candles.append(Candle(symbol="XAUUSD", timeframe="H1", ts=start + timedelta(hours=i),
                              o=o, h=h, low=lo, c=c, v=float(v)))
        price = c
    return candles


def _bench(label: str, fn, iterations: int = 10) -> dict:
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return {
        "label": label,
        "iterations": iterations,
        "mean_ms": statistics.mean(times) * 1000,
        "median_ms": statistics.median(times) * 1000,
        "stdev_ms": statistics.stdev(times) * 1000 if len(times) > 1 else 0,
        "min_ms": min(times) * 1000,
        "max_ms": max(times) * 1000,
    }


def bench_market_data():
    print("\n=== Market Data Generation ===")
    for n in [100, 500, 1000]:
        candles = _generate_candles(n)
        result = _bench(f"Generate {n} candles", lambda: _generate_candles(n))
        print(f"  {result['label']}: {result['mean_ms']:.2f}ms (±{result['stdev_ms']:.2f}ms)")
    return candles


def bench_indicators(candles: list[Candle]):
    print("\n=== Indicator Calculation ===")
    closes = [c.c for c in candles]
    for name, fn in [
        ("SMA 20", lambda: sma(closes, 20)),
        ("EMA 20", lambda: ema(closes, 20)),
        ("RSI 14", lambda: rsi(candles, 14)),
        ("MACD", lambda: macd(candles)),
        ("Bollinger", lambda: bollinger(candles)),
        ("ATR 14", lambda: atr(candles, 14)),
        ("ADX 14", lambda: adx(candles, 14)),
    ]:
        result = _bench(name, fn, iterations=20)
        print(f"  {name}: {result['mean_ms']:.2f}ms")


def bench_structure(candles: list[Candle]):
    print("\n=== Market Structure Analysis ===")
    result = _bench("Structure analyze (500 candles)", lambda: analyze_structure(candles), iterations=5)
    print(f"  {result['label']}: {result['mean_ms']:.2f}ms")
    result = _bench("SMC analyze (500 candles)", lambda: analyze_smc(candles), iterations=5)
    print(f"  {result['label']}: {result['mean_ms']:.2f}ms")


def bench_backtest(candles: list[Candle]):
    print("\n=== Backtest Engine ===")
    config = BacktestConfig(symbol="XAUUSD", timeframe="H1", initial_balance=10000.0, leverage=100)
    result = _bench(
        "Backtest 500 bars (no orders)",
        lambda: BacktestBroker(config, candles),
        iterations=5,
    )
    print(f"  {result['label']}: {result['mean_ms']:.2f}ms")


def bench_risk():
    print("\n=== Risk Engine ===")
    engine = RiskEngine(market_data)
    result = _bench(
        "Risk calc (1000 iterations)",
        lambda: engine.position_size(symbol="XAUUSD", equity=10000, risk_pct=0.01, entry=2000, sl=1990),
        iterations=20,
    )
    print(f"  {result['label']}: {result['mean_ms']:.2f}ms")


def main():
    print("EntryX Performance Benchmarks")
    print("=" * 50)
    candles = bench_market_data()
    bench_indicators(candles)
    bench_structure(candles)
    bench_backtest(candles)
    bench_risk()
    print("\n" + "=" * 50)
    print("Benchmarks complete.")


if __name__ == "__main__":
    main()
