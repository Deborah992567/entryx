"""Security audit log — sanitized; never stores secrets."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base



class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
