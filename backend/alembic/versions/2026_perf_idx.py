"""add performance indexes

Revision ID: 2026_perf_idx
Revises: 883110da4a12
Create Date: 2026-08-21 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "2026_perf_idx"
down_revision: str | None = "883110da4a12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_candles_symbol_tf_ts", "candles", ["symbol", "timeframe", "ts"])
    op.create_index("ix_orders_user_status", "orders", ["user_id", "status"])
    op.create_index("ix_positions_user_symbol", "positions", ["user_id", "symbol"])
    op.create_index("ix_trades_user_ts", "trades", ["user_id", "closed_at"])
    op.create_index("ix_refresh_tokens_user", "refresh_tokens", ["user_id"])
    op.create_index("ix_audit_logs_user_action", "audit_logs", ["user_id", "action"])
    op.create_index("ix_journal_entries_user_ts", "journal_entries", ["user_id", "created_at"])
    op.create_index("ix_alerts_user_active", "alerts", ["user_id", "is_active"])
    op.create_index("ix_ai_conversations_user", "ai_conversations", ["user_id"])
    op.create_index("ix_chart_layouts_user", "chart_layouts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_chart_layouts_user", "chart_layouts")
    op.drop_index("ix_ai_conversations_user", "ai_conversations")
    op.drop_index("ix_alerts_user_active", "alerts")
    op.drop_index("ix_journal_entries_user_ts", "journal_entries")
    op.drop_index("ix_audit_logs_user_action", "audit_logs")
    op.drop_index("ix_refresh_tokens_user", "refresh_tokens")
    op.drop_index("ix_trades_user_ts", "trades")
    op.drop_index("ix_positions_user_symbol", "positions")
    op.drop_index("ix_orders_user_status", "orders")
    op.drop_index("ix_candles_symbol_tf_ts", "candles")
