"""Trading schemas (Phase 2 — paper broker)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=32, description="Trading symbol (e.g. EURUSD)")
    side: str = Field(description="Order side: 'buy' or 'sell'")
    type: str = Field(default="market", description="Order type: market, limit, stop, stop_limit")
    volume: float = Field(gt=0, description="Position volume in lots")
    price: float | None = Field(default=None, description="Price for limit/stop orders")
    limit_price: float | None = Field(default=None, description="Limit price for stop_limit orders")
    sl: float | None = Field(default=None, description="Stop-loss price")
    tp: float | None = Field(default=None, description="Take-profit price")
    magic: int = Field(default=0, description="Expert advisor magic number")
    comment: str = Field(default="", max_length=255, description="Order comment")
    expiry: datetime | None = Field(default=None, description="Pending order expiry time")

    @field_validator("side", "type")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.lower()


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Unique order identifier")
    symbol: str = Field(description="Trading symbol")
    side: str = Field(description="Order side: buy or sell")
    type: str = Field(description="Order type: market, limit, stop, stop_limit")
    volume: float = Field(description="Order volume in lots")
    price: float | None = Field(description="Order price (for limit/stop)")
    limit_price: float | None = Field(default=None, description="Limit price for stop_limit orders")
    state: str = Field(description="Order state: pending, filled, cancelled, expired")
    filled_price: float | None = Field(description="Actual fill price (None if pending)")
    sl: float | None = Field(description="Stop-loss price")
    tp: float | None = Field(description="Take-profit price")
    magic: int = Field(description="Expert advisor magic number")
    comment: str = Field(description="Order comment")
    expiry: datetime | None = Field(default=None, description="Pending order expiry")
    created_at: datetime = Field(description="Order creation timestamp")


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Unique position identifier")
    symbol: str = Field(description="Trading symbol")
    side: str = Field(description="Position direction: buy or sell")
    volume: float = Field(description="Position volume in lots")
    open_price: float = Field(description="Average entry price")
    sl: float | None = Field(description="Stop-loss price")
    tp: float | None = Field(description="Take-profit price")
    opened_at: datetime = Field(description="Position open timestamp")
    commission: float = Field(description="Total commission charged")
    magic: int = Field(default=0, description="Expert advisor magic number")
    trail: float | None = Field(default=None, description="Trailing stop distance")
    floating_pnl: float = Field(default=0.0, description="Current unrealized profit/loss")


class PositionModify(BaseModel):
    sl: float | None = Field(default=None, description="New stop-loss price")
    tp: float | None = Field(default=None, description="New take-profit price")
    trail: float | None = Field(default=None, description="New trailing stop distance")


class PositionClose(BaseModel):
    volume: float | None = Field(default=None, gt=0, description="Volume to close (None = close full position)")


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Unique trade identifier")
    symbol: str = Field(description="Trading symbol")
    side: str = Field(description="Trade direction: buy or sell")
    volume: float = Field(description="Trade volume in lots")
    open_price: float = Field(description="Trade entry price")
    close_price: float = Field(description="Trade exit price")
    gross_pnl: float = Field(description="Gross profit/loss before fees")
    net_pnl: float = Field(description="Net profit/loss after commission and swap")
    commission: float = Field(description="Total commission charged")
    swap: float = Field(default=0.0, description="Total swap/rollover charges")
    closed_at: datetime = Field(description="Trade close timestamp")


class AccountOut(BaseModel):
    number: str = Field(description="Account number")
    currency: str = Field(description="Account currency (USD, EUR, etc)")
    balance: float = Field(description="Account balance (realized PnL included)")
    equity: float = Field(description="Account equity (balance + floating PnL)")
    margin_used: float = Field(description="Total margin used by open positions")
    free_margin: float = Field(description="Available margin for new positions")
    margin_level: float = Field(description="Margin level percentage (equity/margin * 100)")
    floating_pnl: float = Field(description="Total unrealized profit/loss")
    realized_pnl: float = Field(default=0.0, description="Total realized profit/loss")
    commission: float = Field(default=0.0, description="Total commission charged")
    swap: float = Field(default=0.0, description="Total swap/rollover charges")
    exposure: float = Field(default=0.0, description="Total market exposure")


class RiskAssess(BaseModel):
    symbol: str = Field(min_length=1, max_length=32, description="Trading symbol")
    equity: float = Field(gt=0, description="Current account equity")
    risk_pct: float = Field(ge=0, le=100, description="Risk percentage per trade")
    entry: float = Field(description="Proposed entry price")
    sl: float | None = Field(default=None, description="Proposed stop-loss price")
    tp: float | None = Field(default=None, description="Proposed take-profit price")
    leverage: float = Field(default=100.0, gt=0, description="Account leverage")


class RiskAssessmentOut(BaseModel):
    symbol: str = Field(description="Trading symbol")
    lots: float = Field(description="Recommended position size in lots")
    risk_amount: float = Field(description="Risk amount in account currency")
    risk_pct: float = Field(description="Actual risk percentage")
    reward: float = Field(description="Potential reward in account currency")
    rr: float = Field(description="Reward-to-risk ratio")
    margin_required: float = Field(description="Required margin for this position")
    exposure: float = Field(description="Total market exposure if opened")
    min_lots: float = Field(description="Minimum allowed lot size")
    max_lots: float = Field(description="Maximum allowed lot size")


class RiskLimitsOut(BaseModel):
    max_lots_per_order: float = Field(description="Maximum lots per single order")
    max_lots_per_symbol: float = Field(description="Maximum total lots per symbol")
    max_open_positions: int = Field(description="Maximum number of open positions")
    max_risk_pct_per_trade: float = Field(description="Maximum risk percentage per trade")
    min_lots: float = Field(description="Minimum lot size")
