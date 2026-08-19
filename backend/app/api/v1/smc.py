"""Smart Money Concept object routes (Phase 6 line 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.smc import SmcAnalysisOut
from app.services.market_data import market_data
from app.services.smc_objects import analyze_smc

router = APIRouter(prefix="/smc", tags=["smc"])


@router.get("", response_model=SmcAnalysisOut)
def smc_analysis(
    symbol: str,
    tf: str = Query(default="H1", pattern=r"^(M1|M5|M15|M30|H1|H4|D1|W1|MN1)$"),
    limit: int = Query(default=500, ge=50, le=5000),
    _: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    """Deterministic Smart Money Concept object analysis for a symbol/timeframe."""
    try:
        candles = market_data.candles(symbol, tf, limit)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return analyze_smc(candles)
