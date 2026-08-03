"""Paper-trading routes (Phase 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.trading import AccountOut, OrderCreate, OrderOut, PositionOut, TradeOut
from app.services import trading_service
from app.services.broker import BrokerError, OrderRequest

router = APIRouter(prefix="/trading", tags=["trading"])


@router.get("/account", response_model=AccountOut)
def account(user: User = Depends(get_current_user), _db: Session = Depends(get_db)) -> dict:
    return trading_service.account_summary(user.id)


@router.get("/orders", response_model=list[OrderOut])
def list_orders(user: User = Depends(get_current_user), _db: Session = Depends(get_db)) -> list[dict]:
    return [trading_service.to_order_out(o) for o in trading_service.get_broker(user.id).pending_orders()]


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
            sl=body.sl,
            tp=body.tp,
            magic=body.magic,
            comment=body.comment,
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
def list_positions(user: User = Depends(get_current_user), _db: Session = Depends(get_db)) -> list[dict]:
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


@router.get("/history", response_model=list[TradeOut])
def list_history(user: User = Depends(get_current_user), _db: Session = Depends(get_db)) -> list[dict]:
    return [trading_service.to_trade_out(t) for t in trading_service.get_broker(user.id).closed_trades()]
