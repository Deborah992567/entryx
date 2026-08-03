"""Market data routes (Phase 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.market import CandleOut, QuoteOut, SymbolOut
from app.services.market_data import format_candles, format_quote, market_data

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/symbols", response_model=list[SymbolOut])
def list_symbols(
    _: User = Depends(get_current_user), _db: Session = Depends(get_db)
) -> list[SymbolOut]:
    return [SymbolOut.model_validate(s) for s in market_data.symbols()]


@router.get("/candles", response_model=list[CandleOut])
def candles(
    symbol: str,
    tf: str = Query(default="M15", pattern=r"^(M[15]|M15|M30|H1|H4|D1|W1|MN1)$"),
    limit: int = Query(default=500, ge=1, le=5000),
    _: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> list[dict]:
    try:
        return format_candles(market_data.candles(symbol, tf, limit))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/quote", response_model=QuoteOut)
def quote(
    symbol: str,
    _: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    return format_quote(market_data.quote(symbol))
