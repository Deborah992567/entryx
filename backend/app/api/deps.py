"""Shared FastAPI dependencies: DB session, current user, rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import RateLimitError, UnauthorizedError
from app.db.models.user import User
from app.db.session import get_db
from app.services.auth_service import current_user_from_token

# Simple in-memory sliding-window limiter (per-route override via dependency).
_buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    """Sliding-window limiter keyed by (path, ip)."""
    settings = get_settings()
    key = (request.url.path, _client_key(request))
    now = time.monotonic()
    window = _buckets[key]
    window.append(now)
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) > settings.auth_rate_limit_per_minute:
        raise RateLimitError("too many requests — slow down")


def get_current_user(
    authorization: str | None = Header(None), db: Session = Depends(get_db)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    return current_user_from_token(db, token)
