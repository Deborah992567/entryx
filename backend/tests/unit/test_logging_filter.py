"""Tests for the RedactingFilter in logging module."""

from __future__ import annotations

import logging

from app.core.logging import RedactingFilter


def test_redacts_password() -> None:
    f = RedactingFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "password=abc123secret", (), None)
    f.filter(record)
    assert "abc123secret" not in record.msg
    assert "[REDACTED]" in record.msg


def test_redacts_secret_key() -> None:
    f = RedactingFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "secret_key=mykey123", (), None)
    f.filter(record)
    assert "mykey123" not in record.msg
    assert "[REDACTED]" in record.msg


def test_redacts_token() -> None:
    f = RedactingFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "token=eyJhbGciOiJIUzI1NiJ9", (), None)
    f.filter(record)
    assert "eyJhbGciOiJIUzI1NiJ9" not in record.msg


def test_redacts_encryption_key() -> None:
    f = RedactingFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "encryption_key=fernet_key_here", (), None)
    f.filter(record)
    assert "fernet_key_here" not in record.msg


def test_clean_message_unchanged() -> None:
    f = RedactingFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "User logged in successfully", (), None)
    original = record.msg
    f.filter(record)
    assert record.msg == original


def test_redacts_authorization_header() -> None:
    f = RedactingFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9", (), None)
    f.filter(record)
    assert "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9" not in record.msg
