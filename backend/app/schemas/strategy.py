"""Strategy framework schemas (Phase 5)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrategyStart(BaseModel):
    symbol: str = Field(min_length=1, max_length=32, description="Trading symbol (e.g. EURUSD)")
    timeframe: str = Field(default="H1", description="Candle timeframe (M1, M5, H1, D1, etc)")
    candles: int = Field(default=300, ge=10, le=10_000, description="Number of historical candles to load")
    params: dict = Field(default_factory=dict, description="Strategy-specific parameters")


class StrategyInfoOut(BaseModel):
    name: str = Field(description="Strategy identifier")
    description: str = Field(description="Human-readable strategy description")
    params: dict = Field(description="Default parameter values and their types")


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str = Field(description="Signal symbol")
    side: str = Field(description="Signal direction: buy or sell")
    reason: str = Field(description="Human-readable reason for the signal")
    price: float | None = Field(default=None, description="Signal trigger price")
    strength: float = Field(default=1.0, description="Signal strength (0.0-1.0)")
    ts: datetime = Field(description="Signal timestamp")
    meta: dict = Field(default_factory=dict, description="Additional signal metadata")


class StrategyInstanceOut(BaseModel):
    instance_id: str = Field(description="Unique instance identifier")
    strategy: str = Field(description="Strategy name")
    symbol: str = Field(description="Trading symbol")
    timeframe: str = Field(description="Candle timeframe")
    magic: int = Field(description="Magic number for order identification")
    status: str = Field(description="Instance status: running, stopped, error")
    last_error: str = Field(default="", description="Last error message if status is error")
    signals_emitted: list[SignalOut] = Field(default_factory=list, description="Recent signals emitted by this instance")
    orders_placed: int = Field(default=0, description="Total orders placed by this instance")


class StrategyStopOut(BaseModel):
    instance_id: str
    strategy: str
    status: str
    last_error: str = ""
    signals_emitted: list[SignalOut] = Field(default_factory=list)
    orders_placed: int = 0
