"""Smart Money Concept object schemas (Phase 6 line 2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SmcObjectOut(BaseModel):
    kind: str
    bar_index: int
    ts: datetime
    timeframe: str
    direction: str
    range_low: float
    range_high: float
    strength: float = 1.0
    status: str = "active"
    invalidation_price: float | None = None
    meta: dict = Field(default_factory=dict)


class SmcAnalysisOut(BaseModel):
    symbol: str
    timeframe: str
    candles: int
    fvg: list[SmcObjectOut] = Field(default_factory=list)
    displacement: list[SmcObjectOut] = Field(default_factory=list)
    liquidity_pools: list[SmcObjectOut] = Field(default_factory=list)
    sweeps: list[SmcObjectOut] = Field(default_factory=list)
    order_blocks: list[SmcObjectOut] = Field(default_factory=list)
    breaker_blocks: list[SmcObjectOut] = Field(default_factory=list)
    premium_discount: list[SmcObjectOut] = Field(default_factory=list)
