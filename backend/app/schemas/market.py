"""Market data schemas (Phase 2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SymbolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str = Field(description="Trading symbol ticker (e.g. EURUSD)")
    name: str = Field(description="Human-readable instrument name")
    category: str = Field(description="Asset class (forex, commodity, crypto, index)")
    base_currency: str = Field(description="Base currency code")
    quote_currency: str = Field(description="Quote currency code")
    digits: int = Field(description="Price decimal places")
    tick_size: float = Field(description="Minimum price increment")
    contract_size: float = Field(description="Standard contract size in units")
    pip_value: float = Field(description="Value of one pip in account currency")


class CandleOut(BaseModel):
    symbol: str = Field(description="Trading symbol")
    timeframe: str = Field(description="Candle timeframe")
    ts: datetime = Field(description="Candle timestamp")
    o: float = Field(description="Open price")
    h: float = Field(description="High price")
    low: float = Field(alias="l", description="Low price")
    c: float = Field(description="Close price")
    v: float = Field(description="Volume")


class QuoteOut(BaseModel):
    symbol: str = Field(description="Trading symbol")
    ts: datetime = Field(description="Quote timestamp")
    bid: float = Field(description="Bid price")
    ask: float = Field(description="Ask price")
    spread: float = Field(description="Bid-ask spread")
    change_pct: float = Field(description="Price change percentage")
    volume: float = Field(description="Trading volume")
