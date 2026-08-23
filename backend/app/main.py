"""EntryX FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.middleware import RateLimitMiddleware, RequestIDMiddleware, SecurityHeadersMiddleware
from app.services import broadcaster
from app.ws import endpoint
from app.ws.manager import manager

logger = logging.getLogger("entryx.startup")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.is_sqlite:
            from app.db.base import Base
            from app.db.session import engine

            import app.db.models  # noqa: F401 — ensure all models are registered
            Base.metadata.create_all(bind=engine)
        logger.info("EntryX starting up — version 0.9.0")
        broadcast_task = broadcaster.start_broadcasters()
        yield
        logger.info("EntryX shutting down — closing WS connections")
        broadcast_task.cancel()
        await manager.close_all()
        logger.info("EntryX shutdown complete")

    app = FastAPI(
        title=settings.app_name,
        version="0.9.0",
        description="EntryX trading terminal API — real-time market data, paper trading, AI copilot",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)
    app.add_middleware(RequestIDMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router)
    app.include_router(endpoint.router)

    @app.get("/")
    def root() -> dict:
        return {"app": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}

    @app.get("/version")
    def version() -> dict:
        return {"version": "0.9.0", "app": settings.app_name}

    return app


app = create_app()
