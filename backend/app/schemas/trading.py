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
    limit_price: float | None = None
    sl: float | None = None
    tp: float | None = None
    magic: int = 0
    comment: str = Field(default="", max_length=255)
    expiry: datetime | None = None

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
    limit_price: float | None = None
    state: str
    filled_price: float | None
    sl: float | None
    tp: float | None
    magic: int
    comment: str
    expiry: datetime | None = None
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
    magic: int = 0
    trail: float | None = None
    floating_pnl: float = 0.0


class PositionModify(BaseModel):
    sl: float | None = None
    tp: float | None = None
    trail: float | None = None


class PositionClose(BaseModel):
    volume: float | None = Field(default=None, gt=0)


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
    swap: float = 0.0
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
    commission: float = 0.0
    swap: float = 0.0
    exposure: float = 0.0


class RiskAssess(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    equity: float = Field(gt=0)
    risk_pct: float = Field(ge=0, le=100)
    entry: float
    sl: float | None = None
    tp: float | None = None
    leverage: float = Field(default=100.0, gt=0)


class RiskAssessmentOut(BaseModel):
    symbol: str
    lots: float
    risk_amount: float
    risk_pct: float
    reward: float
    rr: float
    margin_required: float
    exposure: float
    min_lots: float
    max_lots: float


class RiskLimitsOut(BaseModel):
    max_lots_per_order: float
    max_lots_per_symbol: float
    max_open_positions: int
    max_risk_pct_per_trade: float
    min_lots: float
