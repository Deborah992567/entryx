"""Market data models: symbols, candles, ticks, coverage metadata."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(32), default="forex")
    base_currency: Mapped[str] = mapped_column(String(16), default="")
    quote_currency: Mapped[str] = mapped_column(String(16), default="")
    digits: Mapped[int] = mapped_column(Integer, default=2)
    contract_size: Mapped[float] = mapped_column(Numeric(20, 6), default=1)
    tick_size: Mapped[float] = mapped_column(Numeric(20, 8), default=0.01)
    tick_value: Mapped[float] = mapped_column(Numeric(20, 8), default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MarketDataMeta(Base):
    __tablename__ = "market_data_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="simulated")
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    first_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    candle_count: Mapped[int] = mapped_column(BigInteger, default=0)


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("symbol_id", "timeframe", "ts", name="uq_candle_symbol_tf_ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    o: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    h: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    l: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    c: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    v: Mapped[float] = mapped_column(Numeric(24, 2), default=0)


class Tick(Base):
    __tablename__ = "ticks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bid: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    ask: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(24, 2), default=0)
