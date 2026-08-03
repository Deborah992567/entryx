"""Market data schemas (Phase 2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SymbolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str
    category: str
    base_currency: str
    quote_currency: str
    digits: int
    tick_size: float
    contract_size: float
    pip_value: float


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
