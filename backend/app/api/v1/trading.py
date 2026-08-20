"""Paper-trading routes (Phase 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.trading import (
    AccountOut,
    OrderCreate,
    OrderOut,
    PositionClose,
    PositionModify,
    PositionOut,
    RiskAssess,
    RiskAssessmentOut,
    RiskLimitsOut,
    TradeOut,
)
from app.services import trading_service
from app.services.broker import BrokerError, OrderRequest
from app.services.market_data import market_data
from app.services.risk_engine import RiskEngine

router = APIRouter(prefix="/trading", tags=["trading"])

risk_engine = RiskEngine(market_data)


@router.get("/account", response_model=AccountOut)
def account(user: User = Depends(get_current_user), _db: Session = Depends(get_db)) -> dict:
    return trading_service.account_summary(user.id)


@router.get("/orders", response_model=list[OrderOut])
def list_orders(
    user: User = Depends(get_current_user), _db: Session = Depends(get_db)
) -> list[dict]:
    return [
        trading_service.to_order_out(o)
        for o in trading_service.get_broker(user.id).pending_orders()
    ]


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreate,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    try:
        request = OrderRequest(
            symbol=body.symbol,
            side=body.side,
            type=body.type,
            volume=body.volume,
            price=body.price,
            limit_price=body.limit_price,
            sl=body.sl,
            tp=body.tp,
            magic=body.magic,
            comment=body.comment,
            expiry=body.expiry,
        )
        order = await trading_service.place_order(user.id, request)
        return trading_service.to_order_out(order)
    except BrokerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/orders/{order_id}", response_model=OrderOut)
async def cancel_order(
    order_id: str,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    try:
        order = await trading_service.cancel_order(user.id, order_id)
        return trading_service.to_order_out(order)
    except BrokerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/positions", response_model=list[PositionOut])
def list_positions(
    user: User = Depends(get_current_user), _db: Session = Depends(get_db)
) -> list[dict]:
    return trading_service.list_positions(user.id)


@router.delete("/positions/{position_id}", response_model=TradeOut)
async def close_position(
    position_id: str,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    try:
        trade = await trading_service.close_position(user.id, position_id)
        return trading_service.to_trade_out(trade)
    except BrokerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/positions/{position_id}/close", response_model=TradeOut)
async def close_position_partial(
    position_id: str,
    body: PositionClose,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    try:
        trade = await trading_service.close_position(user.id, position_id, volume=body.volume)
        return trading_service.to_trade_out(trade)
    except BrokerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/positions/{position_id}", response_model=PositionOut)
async def modify_position(
    position_id: str,
    body: PositionModify,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    try:
        changes = {field: getattr(body, field) for field in body.model_fields_set}
        position = await trading_service.modify_position(user.id, position_id, **changes)
        return trading_service.to_position_out(position)
    except BrokerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/history", response_model=list[TradeOut])
def list_history(
    user: User = Depends(get_current_user), _db: Session = Depends(get_db)
) -> list[dict]:
    return [
        trading_service.to_trade_out(t) for t in trading_service.get_broker(user.id).closed_trades()
    ]


@router.post("/risk/assess", response_model=RiskAssessmentOut)
def assess_risk(
    body: RiskAssess,
    user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    return risk_engine.assess(
        symbol=body.symbol.upper(),
        equity=body.equity,
        risk_pct=body.risk_pct,
        entry=body.entry,
        sl=body.sl,
        tp=body.tp,
        leverage=body.leverage,
    )


@router.get("/risk/limits", response_model=RiskLimitsOut)
def risk_limits(user: User = Depends(get_current_user), _db: Session = Depends(get_db)) -> dict:
    limits = risk_engine.limits
    return {field: getattr(limits, field) for field in RiskLimitsOut.model_fields}
