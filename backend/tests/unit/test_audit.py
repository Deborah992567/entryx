"""Tests for audit service."""

from __future__ import annotations

from app.db.models.audit import AuditLog
from app.services import audit


def test_record_creates_audit_entry(db) -> None:
    audit.record(db, action="test.action", user_id=1, entity="test", entity_id="42", ip="127.0.0.1")
    entries = audit.recent(db, limit=10)
    assert len(entries) >= 1
    latest = entries[0]
    assert latest.action == "test.action"
    assert latest.user_id == 1
    assert latest.entity == "test"
    assert latest.entity_id == "42"
    assert latest.ip == "127.0.0.1"


def test_record_with_detail(db) -> None:
    audit.record(
        db,
        action="test.detail",
        user_id=2,
        detail={"key": "value", "nested": {"a": 1}},
    )
    entries = audit.recent(db, limit=1)
    assert entries[0].detail_json == {"key": "value", "nested": {"a": 1}}


def test_for_user_filters_by_user_id(db) -> None:
    audit.record(db, action="user1.action", user_id=10)
    audit.record(db, action="user2.action", user_id=20)
    audit.record(db, action="user1.action2", user_id=10)
    entries = audit.for_user(db, user_id=10)
    assert all(e.user_id == 10 for e in entries)
    assert len(entries) == 2


def test_by_action_filters(db) -> None:
    audit.record(db, action="login", user_id=1)
    audit.record(db, action="trade", user_id=1)
    audit.record(db, action="login", user_id=2)
    entries = audit.by_action(db, action="login")
    assert all(e.action == "login" for e in entries)
    assert len(entries) == 2


def test_record_without_optional_fields(db) -> None:
    audit.record(db, action="minimal")
    entries = audit.recent(db, limit=1)
    assert entries[0].action == "minimal"
    assert entries[0].user_id is None
    assert entries[0].detail_json == {}
