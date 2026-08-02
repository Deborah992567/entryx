"""Deterministic tests for security primitives."""

from __future__ import annotations

from datetime import UTC

import jwt
import pytest
from app.core import security
from app.core.config import Settings


@pytest.fixture()
def settings() -> Settings:
    from cryptography.fernet import Fernet

    return Settings(
        secret_key="test-secret-key",
        access_token_expire_minutes=15,
        refresh_token_expire_days=30,
        encryption_key=Fernet.generate_key().decode(),
    )


def test_password_hash_roundtrip():
    hashed = security.hash_password("correct horse")
    assert hashed != "correct horse"
    assert security.verify_password("correct horse", hashed) is True
    assert security.verify_password("wrong", hashed) is False


def test_password_hash_is_salted():
    a = security.hash_password("same")
    b = security.hash_password("same")
    assert a != b


def test_verify_password_rejects_garbage():
    assert security.verify_password("x", "not-a-hash") is False


def test_access_token_roundtrip(settings):
    token = security.create_access_token("42", settings, extra={"scope": "trading"})
    payload = security.decode_access_token(token, settings)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert payload["scope"] == "trading"


def test_access_token_rejects_refresh_type(settings):
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    payload = {
        "sub": "42",
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    token = jwt.encode(payload, settings.secret_key.encode(), algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(token, settings)


def test_access_token_tamper_rejected(settings):
    token = security.create_access_token("42", settings)
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(token + "x", settings)


def test_refresh_token_hash(settings):
    raw, token_hash, expires_at = security.create_refresh_token(settings)
    assert security.sha256_hex(raw) == token_hash
    assert raw != token_hash
    assert expires_at is not None


def test_constant_time_compare():
    assert security.constant_time_compare("abc", "abc") is True
    assert security.constant_time_compare("abc", "abd") is False


def test_fernet_encrypt_decrypt_roundtrip(settings):
    encrypted = security.encrypt_secret("broker-password", settings)
    assert "broker-password" not in encrypted
    assert security.decrypt_secret(encrypted, settings) == "broker-password"


def test_fernet_requires_key():
    settings = Settings(secret_key="x", encryption_key="")
    with pytest.raises(ValueError):
        security.encrypt_secret("secret", settings)


def test_decrypt_with_wrong_key_fails():
    from cryptography.fernet import Fernet

    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()
    assert key_a != key_b
    settings_a = Settings(secret_key="x", encryption_key=key_a)
    settings_b = Settings(secret_key="x", encryption_key=key_b)
    encrypted = security.encrypt_secret("secret", settings_a)
    with pytest.raises(ValueError):
        security.decrypt_secret(encrypted, settings_b)
