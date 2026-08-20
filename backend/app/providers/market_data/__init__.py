"""Market data provider adapters — thin wrappers around the core service."""

from __future__ import annotations

from app.services.market_data import MarketDataProvider, market_data

__all__ = ["get_market_data_provider"]


def get_market_data_provider() -> MarketDataProvider:
    """Return the active market data provider instance."""
    return market_data
