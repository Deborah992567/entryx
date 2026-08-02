"""Trading journal entries linked to closed trades."""

from __future__ import annotations

from app.db.base import Base, TimestampMixin
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id", ondelete="SET NULL"))
    notes: Mapped[str] = mapped_column(Text, default="")
    setup_type: Mapped[str] = mapped_column(String(64), default="")
    strategy: Mapped[str] = mapped_column(String(120), default="")
    reason_entry: Mapped[str] = mapped_column(Text, default="")
    reason_exit: Mapped[str] = mapped_column(Text, default="")
    emotional_tag: Mapped[str] = mapped_column(String(32), default="")
    screenshot_path: Mapped[str] = mapped_column(String(512), default="")
