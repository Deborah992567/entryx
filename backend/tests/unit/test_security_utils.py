"""Tests for security primitives."""

from __future__ import annotations

import hashlib

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    JWT_ALGORITHM,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    constant_time_compare,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decrypt_secret,
    encrypt_secret,
    make_fernet,
    sha256_hex,
    verify_password,
)


def _settings() -> Settings:
    return Settings(secret_key="test-secret-key-that-is-long-enough-for-hs256", encryption_key="")


def test_sha256_hex() -> None:
    expected = hashlib.sha256("hello".encode("utf-8")).hexdigest()
    assert sha256_hex("hello") == expected


def test_constant_time_equal() -> None:
    assert constant_time_compare("abc", "abc") is True
    assert constant_time_compare("abc", "xyz") is False


def test_create_and_decode_access_token() -> None:
    s = _settings()
    token = create_access_token("user:1", s)
    payload = decode_access_token(token, s)
    assert payload["sub"] == "user:1"
    assert payload["type"] == TOKEN_TYPE_ACCESS


def test_decode_rejects_refresh_type() -> None:
    s = _settings()
    from datetime import UTC, datetime, timedelta

    payload = {
        "sub": "user:1",
        "type": TOKEN_TYPE_REFRESH,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    token = jwt.encode(payload, s.secret_key.encode(), algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, s)


def test_create_refresh_token_format() -> None:
    s = _settings()
    raw, token_hash, expires_at = create_refresh_token(s)
    assert len(raw) > 40
    assert len(token_hash) == 64
    assert expires_at.year >= 2026


def test_verify_password_roundtrip() -> None:
    from app.core.security import hash_password

    h = hash_password("mypassword")
    assert verify_password("mypassword", h) is True
    assert verify_password("wrongpassword", h) is False


def test_make_fernet_no_key_raises() -> None:
    s = _settings()
    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        make_fernet(s)


def test_encrypt_decrypt_roundtrip() -> None:
    key = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode()
    s = Settings(secret_key="test", encryption_key=key)
    encrypted = encrypt_secret("broker_pass_123", s)
    assert encrypted != "broker_pass_123"
    decrypted = decrypt_secret(encrypted, s)
    assert decrypted == "broker_pass_123"


def test_decrypt_bad_key_raises() -> None:
    key1 = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode()
    key2 = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode()
    s1 = Settings(secret_key="test", encryption_key=key1)
    s2 = Settings(secret_key="test", encryption_key=key2)
    encrypted = encrypt_secret("secret", s1)
    with pytest.raises(ValueError, match="cannot decrypt"):
        decrypt_secret(encrypted, s2)


def test_access_token_with_extra_claims() -> None:
    s = _settings()
    token = create_access_token("user:42", s, extra={"role": "admin", "email": "a@b.com"})
    payload = decode_access_token(token, s)
    assert payload["role"] == "admin"
    assert payload["email"] == "a@b.com"
    assert payload["sub"] == "user:42"


def test_expired_token_rejected() -> None:
    from datetime import UTC, datetime, timedelta

    s = _settings()
    payload = {
        "sub": "1",
        "type": TOKEN_TYPE_ACCESS,
        "iat": datetime.now(UTC) - timedelta(hours=2),
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    token = jwt.encode(payload, s.secret_key.encode(), algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, s)


def test_future_token_rejected() -> None:
    from datetime import UTC, datetime, timedelta

    s = _settings()
    payload = {
        "sub": "1",
        "type": TOKEN_TYPE_ACCESS,
        "iat": datetime.now(UTC) + timedelta(hours=1),
        "exp": datetime.now(UTC) + timedelta(hours=2),
    }
    token = jwt.encode(payload, s.secret_key.encode(), algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, s)
