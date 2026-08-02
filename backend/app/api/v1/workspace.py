"""Workspace layout CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.models.workspace import ChartLayout
from app.db.session import get_db
from app.schemas.workspace import LayoutCreate, LayoutOut, LayoutUpdate
from app.services import workspace_service

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/layouts", response_model=list[LayoutOut])
def list_layouts(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[ChartLayout]:
    return workspace_service.list_layouts(db, user.id)


@router.post("/layouts", response_model=LayoutOut, status_code=status.HTTP_201_CREATED)
def create_layout(
    body: LayoutCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChartLayout:
    return workspace_service.create_layout(
        db, user_id=user.id, name=body.name, layout_json=body.layout_json, is_default=body.is_default
    )


@router.put("/layouts/{layout_id}", response_model=LayoutOut)
def update_layout(
    layout_id: int,
    body: LayoutUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChartLayout:
    return workspace_service.update_layout(db, layout_id=layout_id, user_id=user.id, payload=body.model_dump())


@router.delete("/layouts/{layout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_layout(
    layout_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    workspace_service.delete_layout(db, layout_id=layout_id, user_id=user.id)
