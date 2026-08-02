"""Trading models: orders, positions (open), trades (closed history)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(64), default="")
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # buy | sell
    type: Mapped[str] = mapped_column(String(24), nullable=False)  # market|limit|stop|stop_limit
    volume: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)  # limit/stop price
    entry_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    sl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    tp: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="pending")  # pending|filled|cancelled|expired|rejected
    fill_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    filled_volume: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    magic: Mapped[int] = mapped_column(Integer, default=0)
    comment: Mapped[str] = mapped_column(String(255), default="")
    expiration_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Position(Base, TimestampMixin):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(64), default="")
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    open_price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    sl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    tp: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    commission: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    swap: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    magic: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(20), default="open")  # open|closed
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Trade(Base):
    """A fully closed position, i.e. trading history."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    open_price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    close_price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    sl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    tp: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    gross_pnl: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    net_pnl: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    commission: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    swap: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_reason: Mapped[str] = mapped_column(String(32), default="manual")
    magic: Mapped[int] = mapped_column(Integer, default=0)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
