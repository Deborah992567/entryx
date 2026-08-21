"""Backtest API routes (Phase 5 line 2; optimization added in line 4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.backtest import (
    BacktestResultOut,
    BacktestRun,
    OptimizationResultOut,
    OptimizationRun,
)
from app.services.backtest import (
    BacktestConfig,
    backtest_store,
    run_backtest,
)
from app.services.optimization import (
    OptimizationConfig,
    optimization_store,
    optimize_strategy,
)

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("", response_model=BacktestResultOut, status_code=status.HTTP_201_CREATED, summary="Run a backtest")
def create_backtest(
    body: BacktestRun,
    _user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    config = BacktestConfig(
        symbol=body.symbol,
        timeframe=body.timeframe,
        candle_count=body.candle_count,
        start_ts=body.start_ts,
        end_ts=body.end_ts,
        initial_balance=body.config.initial_balance,
        leverage=body.config.leverage,
        commission_bps=body.config.commission_bps,
        slippage_points=body.config.slippage_points,
        spread_mult=body.config.spread_mult,
        swap_enabled=body.config.swap_enabled,
        margin_enabled=body.config.margin_enabled,
    )
    try:
        result = run_backtest(
            strategy_name=body.strategy,
            symbol=body.symbol,
            timeframe=body.timeframe,
            params=body.params,
            config=config,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return backtest_store.save(_user.id, result)


@router.get("/{backtest_id}", response_model=BacktestResultOut, summary="Get backtest result by ID")
def get_backtest(
    backtest_id: str,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    try:
        return backtest_store.get(user.id, backtest_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/optimize", response_model=OptimizationResultOut, status_code=status.HTTP_201_CREATED, summary="Run parameter optimization")
def optimize_backtest(
    body: OptimizationRun,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    config = OptimizationConfig(
        symbol=body.symbol,
        timeframe=body.timeframe,
        candle_count=body.candle_count,
        start_ts=body.start_ts,
        end_ts=body.end_ts,
        initial_balance=body.config.initial_balance,
        leverage=body.config.leverage,
        commission_bps=body.config.commission_bps,
        slippage_points=body.config.slippage_points,
        spread_mult=body.config.spread_mult,
        swap_enabled=body.config.swap_enabled,
        margin_enabled=body.config.margin_enabled,
    )
    try:
        result = optimize_strategy(
            strategy_name=body.strategy,
            symbol=body.symbol,
            timeframe=body.timeframe,
            param_ranges=body.param_ranges,
            metric=body.metric,
            top_n=body.top_n,
            config=config,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return optimization_store.save(user.id, result)


@router.get("/optimize/{optimization_id}", response_model=OptimizationResultOut, summary="Get optimization result by ID")
def get_optimization(
    optimization_id: str,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    try:
        return optimization_store.get(user.id, optimization_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
