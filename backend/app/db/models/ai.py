"""AI models: conversations, grounded messages, and structured analyses."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin



class AIConversation(Base, TimestampMixin):
    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="New conversation")
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AIMessage(Base, TimestampMixin):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user|assistant|system
    content: Mapped[str] = mapped_column(Text, default="")
    grounded_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model: Mapped[str] = mapped_column(String(80), default="")


class AIAnalysis(Base, TimestampMixin):
    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), default="")
    timeframe: Mapped[str] = mapped_column(String(8), default="H1")
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model: Mapped[str] = mapped_column(String(80), default="")
