"""Health and system status routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import engine, get_db
from app.schemas.health import ComponentStatus, HealthOut
from app.services.broker import BrokerAccount
from app.services.market_data import market_data
from app.ws.manager import manager

router = APIRouter(tags=["system"])

APP_VERSION = "0.1.0"


def active_brokers() -> list[BrokerAccount]:
    from app.services import trading_service

    return [b.account() for b in trading_service.active_brokers()]


def _db_status() -> ComponentStatus:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return ComponentStatus(status="ok", detail={"dialect": engine.dialect.name})
    except Exception as exc:  # pragma: no cover - defensive
        return ComponentStatus(status="down", detail={"error": str(exc)})


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    db = _db_status()
    components = {
        "database": db,
        "market_data": ComponentStatus(
            status="ok",
            detail={"provider": "simulated", "symbols": len(market_data.symbols())},
        ),
        "broker": ComponentStatus(status="ok", detail={"accounts": len(active_brokers())}),
        "ai": ComponentStatus(status="degraded", detail="AI provider not started (Phase 7)"),
    }
    overall = "ok" if all(c.status == "ok" for c in components.values()) else "degraded"
    return HealthOut(
        status=overall,
        app="EntryX",
        version=APP_VERSION,
        components=components,
    )


@router.get("/system/status", response_model=dict)
def system_status(
    _db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> dict:
    return {
        "app": APP_VERSION,
        "components": {
            "database": _db_status().status,
            "market_data": "ok",
            "broker": "ok",
            "ai": "not_started",
        },
        "ws": manager.stats(),
    }


