"""User profile routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/me", response_model=UserOut)
def update_me(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    if "name" in body and isinstance(body["name"], str):
        user.name = body["name"]
    if "preferences" in body and isinstance(body["preferences"], dict):
        user.preferences = body["preferences"]
    db.commit()
    db.refresh(user)
    return user
