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
    symbol: str
    timeframe: str
    ts: datetime
    o: float
    h: float
    low: float = Field(alias="l")  # serialized as `l` to match the event contract
    c: float
    v: float


class QuoteOut(BaseModel):
    symbol: str
    ts: datetime
    bid: float
    ask: float
    spread: float
    change_pct: float
    volume: float
