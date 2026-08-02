"""Audit logging service.

Every security-relevant and trading action is recorded in `audit_logs`.
The `detail` payload is sanitized by callers — never pass secrets here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.audit import AuditLog


def record(
    db: Session,
    *,
    action: str,
    user_id: int | None = None,
    entity: str = "",
    entity_id: str = "",
    detail: dict[str, Any] | None = None,
    ip: str = "",
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else "",
            detail_json=detail or {},
            ip=ip,
        )
    )
    db.commit()


def recent(db: Session, limit: int = 200) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    return list(db.scalars(stmt))
