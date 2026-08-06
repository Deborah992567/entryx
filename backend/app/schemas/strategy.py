"""Strategy framework schemas (Phase 5)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrategyStart(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = "H1"
    candles: int = Field(default=300, ge=10, le=10_000)
    params: dict = Field(default_factory=dict)


class StrategyInfoOut(BaseModel):
    name: str
    description: str
    params: dict


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    side: str
    reason: str
    price: float | None = None
    strength: float = 1.0
    ts: datetime
    meta: dict = Field(default_factory=dict)


class StrategyInstanceOut(BaseModel):
    instance_id: str
    strategy: str
    symbol: str
    timeframe: str
    magic: int
    status: str
    last_error: str = ""
    signals_emitted: list[SignalOut] = Field(default_factory=list)
    orders_placed: int = 0


class StrategyStopOut(BaseModel):
    instance_id: str
    strategy: str
    status: str
    last_error: str = ""
    signals_emitted: list[SignalOut] = Field(default_factory=list)
    orders_placed: int = 0
