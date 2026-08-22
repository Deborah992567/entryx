"""Tests for market data provider adapter."""

from __future__ import annotations

from app.providers.market_data import get_market_data_provider


def test_get_market_data_provider_returns_singleton() -> None:
    p1 = get_market_data_provider()
    p2 = get_market_data_provider()
    assert p1 is p2


def test_provider_has_symbols() -> None:
    provider = get_market_data_provider()
    symbols = provider.symbols()
    assert len(symbols) > 0
    assert all(hasattr(s, "symbol") for s in symbols)


def test_provider_symbol_info() -> None:
    provider = get_market_data_provider()
    info = provider.symbol_info("EURUSD")
    assert info.symbol == "EURUSD"
    assert info.digits > 0
    assert info.tick_size > 0
    assert info.contract_size > 0
