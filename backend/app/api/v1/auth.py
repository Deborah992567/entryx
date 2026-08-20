"""Auth API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> User:
    rate_limit(request)
    return auth_service.register(
        db,
        email=body.email,
        password=body.password,
        name=body.name,
        ip=request.client.host if request.client else "",
    )


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    rate_limit(request)
    user = auth_service.authenticate(db, email=body.email, password=body.password)
    return auth_service.issue_tokens(
        db,
        user,
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    rate_limit(request)
    return auth_service.refresh(
        db, raw_refresh=body.refresh_token, ip=request.client.host if request.client else ""
    )


@router.post("/logout", status_code=204)
def logout(
    body: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    auth_service.logout(
        db,
        raw_refresh=body.refresh_token,
        user_id=user.id,
        ip=request.client.host if request.client else "",
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
