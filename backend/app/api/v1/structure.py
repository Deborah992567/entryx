"""Market structure detection routes (Phase 6 line 1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.structure import StructureAnalysisOut
from app.services.market_data import market_data
from app.services.market_structure import analyze

router = APIRouter(prefix="/structure", tags=["structure"])


@router.get("", response_model=StructureAnalysisOut)
def market_structure(
    symbol: str,
    tf: str = Query(default="H1", pattern=r"^(M1|M5|M15|M30|H1|H4|D1|W1|MN1)$"),
    limit: int = Query(default=500, ge=50, le=5000),
    left: int = Query(default=5, ge=1, le=20),
    right: int = Query(default=2, ge=0, le=20),
    _: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    """Deterministic market-structure analysis for a symbol/timeframe."""
    try:
        candles = market_data.candles(symbol, tf, limit)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return analyze(candles, left=left, right=right)
