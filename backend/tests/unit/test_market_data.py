"""Tests for the market data provider abstraction and simulated provider."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.services.market_data import (
    Quote,
    market_data,
    next_quote,
    timeframe_minutes,
)


def test_timeframe_minutes_supports_all_common_tfs() -> None:
    assert timeframe_minutes("M1") == 1
    assert timeframe_minutes("m15") == 15
    assert timeframe_minutes("H4") == 240
    assert timeframe_minutes("W1") == 10080
    with pytest.raises(ValueError):
        timeframe_minutes("XX")


def test_symbols_returns_catalog() -> None:
    symbols = market_data.symbols()
    assert len(symbols) >= 10
    assert {s.symbol for s in symbols} >= {"EURUSD", "XAUUSD", "BTCUSD"}


def test_unknown_symbol_raises() -> None:
    with pytest.raises(KeyError):
        market_data.symbol_info("NOPE")
    with pytest.raises(KeyError):
        market_data.candles("NOPE", "M5", 10)


def test_candles_are_deterministic() -> None:
    end = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    first = market_data.candles("EURUSD", "M15", 20, end)
    second = market_data.candles("EURUSD", "M15", 20, end)
    assert [c.c for c in first] == [c.c for c in second]
    assert [c.ts for c in first] == [c.ts for c in second]


def test_candles_are_timeframe_aligned_and_ascending() -> None:
    candles = market_data.candles("USDJPY", "H1", 10)
    assert candles[0].ts.minute == 0 and candles[0].ts.second == 0
    assert all(a.ts < b.ts for a, b in zip(candles, candles[1:], strict=False))


def test_candle_ohlc_invariants() -> None:
    for candle in market_data.candles("XAUUSD", "M5", 50):
        assert candle.low <= min(candle.o, candle.c)
        assert candle.h >= max(candle.o, candle.c)
        assert candle.h >= candle.low
        assert candle.v > 0


def test_quote_shape_and_spread() -> None:
    quote = market_data.quote("GBPUSD")
    assert isinstance(quote, Quote)
    assert quote.bid < quote.ask
    assert quote.spread == pytest.approx(quote.ask - quote.bid)


def test_next_quote_is_close_to_deterministic_quote() -> None:
    base = market_data.quote("EURUSD")
    tick = next_quote("EURUSD")
    assert abs(tick.bid - base.bid) < 0.005
    assert tick.symbol == "EURUSD"
