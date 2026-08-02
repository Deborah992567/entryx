"""Workspace models: persisted chart/panel layouts and chart drawings."""

from __future__ import annotations

from app.db.base import Base, TimestampMixin
from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class ChartLayout(Base, TimestampMixin):
    __tablename__ = "chart_layouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    layout_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Drawing(Base, TimestampMixin):
    __tablename__ = "drawings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    layout_id: Mapped[int | None] = mapped_column(
        ForeignKey("chart_layouts.id", ondelete="SET NULL"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(32), default="")
    timeframe: Mapped[str] = mapped_column(String(8), default="H1")
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    points_json: Mapped[dict] = mapped_column(JSON, default=dict)
    style_json: Mapped[dict] = mapped_column(JSON, default=dict)
