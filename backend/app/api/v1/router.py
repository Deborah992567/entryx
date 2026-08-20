"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    ai,
    auth,
    backtests,
    health,
    market,
    safeguards,
    smc,
    strategies,
    structure,
    trading,
    users,
    workspace,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(ai.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(workspace.router)
api_router.include_router(market.router)
api_router.include_router(trading.router)
api_router.include_router(strategies.router)
api_router.include_router(backtests.router)
api_router.include_router(structure.router)
api_router.include_router(safeguards.router)
api_router.include_router(smc.router)
api_router.include_router(health.router)
