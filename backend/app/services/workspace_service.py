"""Workspace layout persistence service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models.workspace import ChartLayout


def list_layouts(db: Session, user_id: int) -> list[ChartLayout]:
    stmt = (
        select(ChartLayout)
        .where(ChartLayout.user_id == user_id)
        .order_by(ChartLayout.is_default.desc(), ChartLayout.id.asc())
    )
    return list(db.scalars(stmt))


def create_layout(
    db: Session, *, user_id: int, name: str, layout_json: dict, is_default: bool = False
) -> ChartLayout:
    if is_default:
        _clear_default(db, user_id)
    layout = ChartLayout(user_id=user_id, name=name, layout_json=layout_json, is_default=is_default)
    db.add(layout)
    db.commit()
    db.refresh(layout)
    return layout


def update_layout(db: Session, *, layout_id: int, user_id: int, payload: dict) -> ChartLayout:
    layout = _get_owned(db, layout_id, user_id)
    if "name" in payload and payload["name"] is not None:
        layout.name = payload["name"]
    if "layout_json" in payload and payload["layout_json"] is not None:
        layout.layout_json = payload["layout_json"]
    if "is_default" in payload and payload["is_default"] is not None:
        if payload["is_default"]:
            _clear_default(db, user_id)
        layout.is_default = payload["is_default"]
    db.commit()
    db.refresh(layout)
    return layout


def delete_layout(db: Session, *, layout_id: int, user_id: int) -> None:
    layout = _get_owned(db, layout_id, user_id)
    db.delete(layout)
    db.commit()


def _get_owned(db: Session, layout_id: int, user_id: int) -> ChartLayout:
    layout = db.get(ChartLayout, layout_id)
    if not layout or layout.user_id != user_id:
        raise NotFoundError("layout not found")
    return layout


def _clear_default(db: Session, user_id: int) -> None:
    stmt = select(ChartLayout).where(
        ChartLayout.user_id == user_id, ChartLayout.is_default.is_(True)
    )
    for layout in db.scalars(stmt):
        layout.is_default = False
    db.flush()
