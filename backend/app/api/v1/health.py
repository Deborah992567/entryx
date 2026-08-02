"""Health and system status routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import engine, get_db
from app.schemas.health import ComponentStatus, HealthOut

router = APIRouter(tags=["system"])

APP_VERSION = "0.1.0"


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
        "market_data": ComponentStatus(status="degraded", detail="provider not started (Phase 2)"),
        "broker": ComponentStatus(status="degraded", detail="paper broker not started (Phase 2)"),
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
            "market_data": "not_started",
            "broker": "not_started",
            "ai": "not_started",
        },
        "ws": {"connections": 0, "channels": 0},
    }


