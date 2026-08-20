"""Workspace layout + chart drawing CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.models.workspace import ChartLayout, Drawing
from app.db.session import get_db
from app.schemas.workspace import (
    DrawingOut,
    DrawingsSync,
    LayoutCreate,
    LayoutOut,
    LayoutUpdate,
)
from app.services import drawing_service, workspace_service

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
        db,
        user_id=user.id,
        name=body.name,
        layout_json=body.layout_json,
        is_default=body.is_default,
    )


@router.put("/layouts/{layout_id}", response_model=LayoutOut)
def update_layout(
    layout_id: int,
    body: LayoutUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChartLayout:
    return workspace_service.update_layout(
        db, layout_id=layout_id, user_id=user.id, payload=body.model_dump()
    )


@router.delete("/layouts/{layout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_layout(
    layout_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    workspace_service.delete_layout(db, layout_id=layout_id, user_id=user.id)


@router.get("/drawings", response_model=list[DrawingOut])
def list_drawings(
    symbol: str = Query(min_length=1, max_length=32),
    timeframe: str = Query(min_length=1, max_length=8),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Drawing]:
    return drawing_service.list_drawings(db, user_id=user.id, symbol=symbol, timeframe=timeframe)


@router.put("/drawings", response_model=list[DrawingOut])
def sync_drawings(
    body: DrawingsSync,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Drawing]:
    return drawing_service.replace_drawings(
        db,
        user_id=user.id,
        symbol=body.symbol,
        timeframe=body.timeframe,
        items=body.drawings,
    )


@router.delete("/drawings", status_code=status.HTTP_204_NO_CONTENT)
def clear_drawings(
    symbol: str = Query(min_length=1, max_length=32),
    timeframe: str = Query(min_length=1, max_length=8),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    drawing_service.clear_drawings(db, user_id=user.id, symbol=symbol, timeframe=timeframe)
