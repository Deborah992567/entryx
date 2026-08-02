"""Strategy and backtest models."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin



class Strategy(Base, TimestampMixin):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    source_code: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(16), default="python")
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    rules_json: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_profile_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Backtest(Base, TimestampMixin):
    __tablename__ = "backtests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id", ondelete="SET NULL"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), default="")
    timeframe: Mapped[str] = mapped_column(String(8), default="H1")
    range_json: Mapped[dict] = mapped_column(JSON, default=dict)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    equity_curve_json: Mapped[dict] = mapped_column(JSON, default=dict)
    trades_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
