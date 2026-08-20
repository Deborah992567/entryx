"""Live broker adapter interface.

Extends the core BrokerAdapter with connection management and
exchange-specific features needed for real trading.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.services.broker import BrokerAdapter


@dataclass(frozen=True)
class BrokerConnection:
    """Status of a live broker connection."""

    status: str  # "connected" | "disconnected" | "error"
    broker: str  # "mt5" | "ctrader" | "oanda" | etc.
    account_id: str = ""
    balance: float = 0.0
    equity: float = 0.0
    error: str = ""


class LiveBrokerAdapter(BrokerAdapter, ABC):
    """Extended interface for live broker adapters.

    Adds connection lifecycle and streaming on top of the base
    BrokerAdapter used by the paper broker.
    """

    @abstractmethod
    async def connect(self, config: dict) -> BrokerConnection:
        """Establish connection to the live broker."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the broker connection."""

    @abstractmethod
    async def connection_status(self) -> BrokerConnection:
        """Return current connection status."""

    @abstractmethod
    async def stream_ticks(self, symbols: list[str]):
        """Yield real-time tick data for the given symbols."""

    @abstractmethod
    async def stream_candles(self, symbol: str, timeframe: str):
        """Yield real-time candle updates."""
