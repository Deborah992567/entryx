"""Backtest schemas (Phase 5 line 2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BacktestConfigIn(BaseModel):
    initial_balance: float = Field(default=100_000, ge=100, le=1_000_000_000)
    leverage: int = Field(default=100, ge=1, le=1000)
    commission_bps: float = Field(default=2.0, ge=0, le=1000)
    slippage_points: float = Field(default=0.0, ge=0, le=1_000_000)
    spread_mult: float = Field(default=1.0, ge=0, le=100)
    swap_enabled: bool = True
    margin_enabled: bool = True


class BacktestRun(BaseModel):
    strategy: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = "H1"
    candle_count: int = Field(default=1000, ge=10, le=50_000)
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    params: dict = Field(default_factory=dict)
    config: BacktestConfigIn = Field(default_factory=BacktestConfigIn)


class BacktestEquityPointOut(BaseModel):
    ts: datetime
    equity: float


class BacktestTradeOut(BaseModel):
    id: str
    symbol: str
    side: str
    volume: float
    open_price: float
    close_price: float
    gross_pnl: float
    net_pnl: float
    commission: float
    swap: float
    opened_at: datetime
    closed_at: datetime
    magic: int = 0


class BacktestResultOut(BaseModel):
    id: str
    strategy: str
    symbol: str
    timeframe: str
    status: str
    last_error: str = ""
    started_at: datetime
    finished_at: datetime
    config: dict
    metrics: dict
    equity_curve: list[BacktestEquityPointOut]
    trades: list[BacktestTradeOut]
