"""Backtest schemas (Phase 5 line 2; optimization added in line 4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BacktestConfigIn(BaseModel):
    initial_balance: float = Field(default=100_000, ge=100, le=1_000_000_000, description="Starting account balance")
    leverage: int = Field(default=100, ge=1, le=1000, description="Account leverage multiplier")
    commission_bps: float = Field(default=2.0, ge=0, le=1000, description="Commission in basis points")
    slippage_points: float = Field(default=0.0, ge=0, le=1_000_000, description="Slippage in points")
    spread_mult: float = Field(default=1.0, ge=0, le=100, description="Spread multiplier (1.0 = normal)")
    swap_enabled: bool = Field(default=True, description="Enable overnight swap/rollover charges")
    margin_enabled: bool = Field(default=True, description="Enable margin calculations")


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


class BacktestMetricsOut(BaseModel):
    start_balance: float
    end_balance: float
    net_profit: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None = None
    expectancy: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe: float | None = None


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
    open_bar: int | None = None
    close_bar: int | None = None
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
    metrics: BacktestMetricsOut
    equity_curve: list[BacktestEquityPointOut]
    trades: list[BacktestTradeOut]


class OptimizationRun(BaseModel):
    strategy: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = "H1"
    candle_count: int = Field(default=1000, ge=10, le=50_000)
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    metric: str = "net_profit"
    top_n: int = Field(default=20, ge=1, le=200)
    param_ranges: dict[str, dict[str, Any]]
    config: BacktestConfigIn = Field(default_factory=BacktestConfigIn)


class OptimizationEntryOut(BaseModel):
    rank: int
    params: dict[str, Any]
    metrics: BacktestMetricsOut


class OptimizationWalkForwardOut(BaseModel):
    first_half: BacktestMetricsOut
    second_half: BacktestMetricsOut


class OptimizationResultOut(BaseModel):
    id: str
    strategy: str
    symbol: str
    timeframe: str
    candle_count: int
    metric: str
    top_n: int
    combinations: int
    started_at: datetime
    finished_at: datetime
    config: dict
    overfit_score: float
    overfit_label: str
    warnings: list[str]
    walk_forward: OptimizationWalkForwardOut | None = None
    best: dict[str, Any]
    results: list[OptimizationEntryOut]
