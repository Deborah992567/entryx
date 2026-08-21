"""Audit logging service.

Every security-relevant and trading action is recorded in `audit_logs`.
The `detail` payload is sanitized by callers — never pass secrets here.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.audit import AuditLog

_audit_log = logging.getLogger("entryx.audit")


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
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else "",
        detail_json=detail or {},
        ip=ip,
    )
    db.add(entry)
    db.commit()
    _audit_log.info(
        "action=%s entity=%s user=%s ip=%s",
        action,
        entity,
        user_id,
        ip,
    )


def recent(db: Session, limit: int = 200) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    return list(db.scalars(stmt))


def for_user(db: Session, user_id: int, limit: int = 100) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def by_action(db: Session, action: str, limit: int = 100) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.action == action)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
