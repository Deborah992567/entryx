"""Trading schemas (Phase 2 — paper broker)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: str
    type: str = "market"
    volume: float = Field(gt=0)
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    magic: int = 0
    comment: str = Field(default="", max_length=255)

    @field_validator("side", "type")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.lower()


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol: str
    side: str
    type: str
    volume: float
    price: float | None
    state: str
    filled_price: float | None
    sl: float | None
    tp: float | None
    magic: int
    comment: str
    created_at: datetime


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol: str
    side: str
    volume: float
    open_price: float
    sl: float | None
    tp: float | None
    opened_at: datetime
    commission: float
    floating_pnl: float = 0.0


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol: str
    side: str
    volume: float
    open_price: float
    close_price: float
    gross_pnl: float
    net_pnl: float
    commission: float
    closed_at: datetime


class AccountOut(BaseModel):
    number: str
    currency: str
    balance: float
    equity: float
    margin_used: float
    free_margin: float
    margin_level: float
    floating_pnl: float
    realized_pnl: float = 0.0
