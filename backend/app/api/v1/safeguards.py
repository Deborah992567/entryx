"""Live trading safeguards API routes (Phase 9).

Configuration, status, and control endpoints for the safety layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.db.models.user import User

router = APIRouter(prefix="/safeguards", tags=["safeguards"])


class SafeguardConfigOut(BaseModel):
    live_enabled: bool
    require_confirmation: bool
    max_position_size: float
    max_daily_loss_pct: float
    max_open_positions: int
    max_order_value: float
    allowed_symbols: list[str]
    blocked_symbols: list[str]
    kill_switch: bool
    paper_validate_first: bool


class SafeguardConfigUpdate(BaseModel):
    live_enabled: bool | None = None
    require_confirmation: bool | None = None
    max_position_size: float | None = None
    max_daily_loss_pct: float | None = None
    max_open_positions: int | None = None
    max_order_value: float | None = None
    allowed_symbols: list[str] | None = None
    blocked_symbols: list[str] | None = None
    kill_switch: bool | None = None
    paper_validate_first: bool | None = None


class KillSwitchRequest(BaseModel):
    active: bool


# In-memory config for now; persists across requests within the same process.
_config = SafeguardConfigOut(
    live_enabled=False,
    require_confirmation=True,
    max_position_size=10.0,
    max_daily_loss_pct=5.0,
    max_open_positions=10,
    max_order_value=100000.0,
    allowed_symbols=[],
    blocked_symbols=[],
    kill_switch=False,
    paper_validate_first=True,
)


@router.get("", response_model=SafeguardConfigOut)
def get_safeguards(user: User = Depends(get_current_user)) -> SafeguardConfigOut:
    return _config


@router.put("", response_model=SafeguardConfigOut)
def update_safeguards(
    body: SafeguardConfigUpdate,
    user: User = Depends(get_current_user),
) -> SafeguardConfigOut:
    global _config
    data = _config.model_dump()
    updates = body.model_dump(exclude_none=True)
    data.update(updates)
    _config = SafeguardConfigOut(**data)
    return _config


@router.post("/kill-switch", response_model=SafeguardConfigOut)
def toggle_kill_switch(
    body: KillSwitchRequest,
    user: User = Depends(get_current_user),
) -> SafeguardConfigOut:
    global _config
    _config = _config.model_copy(update={"kill_switch": body.active})
    return _config


@router.get("/status")
def safeguards_status(user: User = Depends(get_current_user)) -> dict:
    return {
        "live_enabled": _config.live_enabled,
        "kill_switch": _config.kill_switch,
        "safeguards_active": _config.require_confirmation,
        "max_daily_loss_pct": _config.max_daily_loss_pct,
    }
