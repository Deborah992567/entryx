"""Market structure detection schemas (Phase 6)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StructureObjectOut(BaseModel):
    kind: str
    bar_index: int
    ts: datetime
    price: float
    timeframe: str
    direction: str
    status: str
    strength: float = 1.0
    invalidation_price: float | None = None
    meta: dict = Field(default_factory=dict)


class StructureAnalysisOut(BaseModel):
    symbol: str
    timeframe: str
    candles: int
    left: int
    right: int
    swings: list[StructureObjectOut] = Field(default_factory=list)
    bos: list[StructureObjectOut] = Field(default_factory=list)
    choch: list[StructureObjectOut] = Field(default_factory=list)
    regimes: list[StructureObjectOut] = Field(default_factory=list)
    breakouts: list[StructureObjectOut] = Field(default_factory=list)
    retests: list[StructureObjectOut] = Field(default_factory=list)
