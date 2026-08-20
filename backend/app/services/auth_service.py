"""Authentication service: register, login, refresh, logout, current-user.

Refresh tokens are stored hashed (SHA-256). Access tokens are short-lived JWTs.
All auth events are written to the audit log with sanitized detail.
"""

from __future__ import annotations

from datetime import UTC, datetime

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.db.models.user import RefreshToken, User
from app.services import audit

_MISSING_USER = "invalid credentials"
_ERR_ALREADY_REGISTERED = "an account with this email already exists"


def register(db: Session, *, email: str, password: str, name: str, ip: str = "") -> User:
    existing = db.scalar(select(User).where(User.email == email.lower()))
    if existing:
        raise ConflictError(_ERR_ALREADY_REGISTERED)
    user = User(
        email=email.lower(),
        password_hash=security.hash_password(password),
        name=name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit.record(
        db, action="auth.register", user_id=user.id, entity="users", entity_id=user.id, ip=ip
    )
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not security.verify_password(password, user.password_hash):
        raise UnauthorizedError(_MISSING_USER)
    if not user.is_active:
        raise UnauthorizedError("account is disabled")
    return user


def issue_tokens(db: Session, user: User, *, ip: str = "", user_agent: str = "") -> dict:
    settings = get_settings()
    access = security.create_access_token(str(user.id), settings)
    raw_refresh, token_hash, expires_at = security.create_refresh_token(settings)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip=ip,
            user_agent=user_agent[:255],
        )
    )
    db.commit()
    audit.record(db, action="auth.login", user_id=user.id, entity="users", entity_id=user.id, ip=ip)
    return {
        "access_token": access,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


def refresh(db: Session, *, raw_refresh: str, ip: str = "") -> dict:
    settings = get_settings()
    token_hash = security.sha256_hex(raw_refresh)
    token = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None)
        )
    )
    if not token:
        raise UnauthorizedError("invalid or expired refresh token")
    now = datetime.now(UTC)
    if token.expires_at.replace(tzinfo=UTC) < now:
        raise UnauthorizedError("refresh token expired")
    user = db.get(User, token.user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("account is disabled")

    token.revoked_at = now  # rotate: one-time use
    db.commit()
    audit.record(
        db, action="auth.refresh", user_id=user.id, entity="users", entity_id=user.id, ip=ip
    )

    access = security.create_access_token(str(user.id), settings)
    raw_new, token_hash_new, expires_at = security.create_refresh_token(settings)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash_new,
            expires_at=expires_at,
            ip=ip,
        )
    )
    db.commit()
    return {
        "access_token": access,
        "refresh_token": raw_new,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


def logout(db: Session, *, raw_refresh: str, user_id: int, ip: str = "") -> None:
    token_hash = security.sha256_hex(raw_refresh)
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if token and token.user_id == user_id:
        token.revoked_at = datetime.now(UTC)
        db.commit()
    audit.record(
        db, action="auth.logout", user_id=user_id, entity="users", entity_id=user_id, ip=ip
    )


def current_user_from_token(db: Session, access_token: str) -> User:
    settings = get_settings()
    try:
        payload = security.decode_access_token(access_token, settings)
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("invalid or expired access token") from exc
    user_id = int(payload["sub"])
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("account not found or disabled")
    return user


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)
