"""Tests for technical indicators module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.indicators import atr, ema, rsi, sma
from app.services.market_data import Candle


def _prices(n: int = 50) -> list[float]:
    return [100.0 + (i % 10) * 0.5 for i in range(n)]


def _make_candles(n: int = 50) -> list[Candle]:
    now = datetime.now(UTC)
    candles = []
    for i in range(n):
        c = 100.0 + (i % 10) * 0.5
        candles.append(Candle(
            symbol="EURUSD", timeframe="H1",
            ts=now - timedelta(hours=n - i),
            o=c, h=c + 0.5, low=c - 0.5, c=c, v=100.0,
        ))
    return candles


def test_sma_basic() -> None:
    result = sma(_prices(), 10)
    assert len(result) == 50
    non_none = [v for v in result if v is not None]
    assert len(non_none) == 41


def test_sma_period_equals_length() -> None:
    prices = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = sma(prices, 5)
    non_none = [v for v in result if v is not None]
    assert len(non_none) == 1
    assert non_none[0] == 3.0


def test_sma_invalid_period() -> None:
    import pytest
    with pytest.raises(ValueError):
        sma(_prices(), 0)


def test_ema_basic() -> None:
    result = ema(_prices(), 10)
    non_none = [v for v in result if v is not None]
    assert len(non_none) > 0


def test_ema_length_matches_input() -> None:
    prices = _prices(20)
    result = ema(prices, 10)
    assert len(result) == len(prices)


def test_rsi_basic() -> None:
    candles = _make_candles(30)
    result = rsi(candles, 14)
    non_none = [v for v in result if v is not None]
    assert len(non_none) > 0
    assert all(0 <= v <= 100 for v in non_none)


def test_rsi_all_same_prices() -> None:
    now = datetime.now(UTC)
    candles = [
        Candle(symbol="X", timeframe="H1", ts=now - timedelta(hours=i), o=50.0, h=50.0, low=50.0, c=50.0, v=1.0)
        for i in range(20, 0, -1)
    ]
    result = rsi(candles, 14)
    non_none = [v for v in result if v is not None]
    assert len(non_none) > 0
    assert all(v == 100.0 for v in non_none)


def test_atr_basic() -> None:
    candles = _make_candles(30)
    result = atr(candles, 14)
    non_none = [v for v in result if v is not None]
    assert len(non_none) > 0
    assert all(v >= 0 for v in non_none)
