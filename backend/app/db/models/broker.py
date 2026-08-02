"""Broker and account models.

Accounts carry an `environment` flag ("PAPER"|"LIVE") that isolates trading
domains. Broker credentials are stored encrypted and never exposed via API.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin



class Broker(Base, TimestampMixin):
    __tablename__ = "brokers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    accounts: Mapped[list[Account]] = relationship(back_populates="broker")


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    broker_id: Mapped[int | None] = mapped_column(ForeignKey("brokers.id", ondelete="SET NULL"))
    number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False, default="PAPER")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    balance: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    leverage: Mapped[float] = mapped_column(Numeric(10, 2), default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_live_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    broker: Mapped[Broker | None] = relationship(back_populates="accounts")
