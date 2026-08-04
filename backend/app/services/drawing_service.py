"""Chart drawing persistence service.

Drawings are scoped per (user, symbol, timeframe) and synced whole-chart: the
client PUTs the full set for a chart and the server replaces it atomically.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.workspace import Drawing
from app.schemas.workspace import DrawingIn


def list_drawings(
    db: Session, *, user_id: int, symbol: str, timeframe: str
) -> list[Drawing]:
    stmt = (
        select(Drawing)
        .where(
            Drawing.user_id == user_id,
            Drawing.symbol == symbol,
            Drawing.timeframe == timeframe,
        )
        .order_by(Drawing.id.asc())
    )
    return list(db.scalars(stmt))


def replace_drawings(
    db: Session, *, user_id: int, symbol: str, timeframe: str, items: Sequence[DrawingIn]
) -> list[Drawing]:
    """Replaces all drawings for a chart with [items] in a single transaction."""
    db.execute(
        delete(Drawing).where(
            Drawing.user_id == user_id,
            Drawing.symbol == symbol,
            Drawing.timeframe == timeframe,
        )
    )
    drawings = [
        Drawing(
            user_id=user_id,
            symbol=symbol,
            timeframe=timeframe,
            kind=item.kind,
            points_json=item.points_json,
            style_json=item.style_json,
        )
        for item in items
    ]
    db.add_all(drawings)
    db.commit()
    for drawing in drawings:
        db.refresh(drawing)
    return drawings


def clear_drawings(db: Session, *, user_id: int, symbol: str, timeframe: str) -> None:
    db.execute(
        delete(Drawing).where(
            Drawing.user_id == user_id,
            Drawing.symbol == symbol,
            Drawing.timeframe == timeframe,
        )
    )
    db.commit()
