"""Strategy framework routes (Phase 5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.strategy import (
    StrategyInfoOut,
    StrategyInstanceOut,
    StrategyStart,
    StrategyStopOut,
)
from app.services import trading_service
from app.services.market_data import market_data
from app.services.strategy import strategy_engine

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyInfoOut])
def list_strategies(
    _user: User = Depends(get_current_user), _db: Session = Depends(get_db)
) -> list[dict]:
    return strategy_engine.catalog()


@router.get("/instances", response_model=list[StrategyInstanceOut])
def list_instances(
    user: User = Depends(get_current_user), _db: Session = Depends(get_db)
) -> list[dict]:
    return strategy_engine.instances(user.id)


@router.post(
    "/{name}/start", response_model=StrategyInstanceOut, status_code=status.HTTP_201_CREATED
)
def start_strategy(
    name: str,
    body: StrategyStart,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    broker = trading_service.get_broker(user.id)
    try:
        return strategy_engine.start(
            user_id=user.id,
            name=name,
            symbol=body.symbol,
            provider=market_data,
            broker=broker,
            params=body.params,
            timeframe=body.timeframe,
            candles=body.candles,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/instances/{instance_id}/stop", response_model=StrategyStopOut)
def stop_strategy(
    instance_id: str,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    try:
        return strategy_engine.stop(user.id, instance_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
