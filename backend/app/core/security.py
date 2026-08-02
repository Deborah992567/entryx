"""Security primitives: password hashing, JWT creation/validation, token hashing.

- Passwords: Argon2id via argon2-cffi.
- Access tokens: short-lived JWT (HS256) with subject + type claim.
- Refresh tokens: opaque random value; only its SHA-256 hash is stored.
- Broker credentials: AES via Fernet (key from ENCRYPTION_KEY).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings

_pwd_hasher = PasswordHasher()

JWT_ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def hash_password(password: str) -> str:
    return _pwd_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def _secret(settings: Settings) -> bytes:
    return settings.secret_key.encode()


def create_access_token(
    subject: str, settings: Settings, extra: dict[str, Any] | None = None
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": TOKEN_TYPE_ACCESS,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _secret(settings), algorithm=JWT_ALGORITHM)


def create_refresh_token(settings: Settings) -> tuple[str, str, datetime]:
    """Return (raw_token, token_hash, expires_at). Only the hash is persisted."""
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    return raw, sha256_hex(raw), expires_at


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Raise jwt.InvalidTokenError on any failure; enforce type=access."""
    payload = jwt.decode(token, _secret(settings), algorithms=[JWT_ALGORITHM])
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise jwt.InvalidTokenError("token type is not access")
    return payload


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def make_fernet(settings: Settings) -> Fernet:
    key = settings.encryption_key.encode() if settings.encryption_key else b""
    if not key:
        raise ValueError("ENCRYPTION_KEY is not configured")
    return Fernet(key)


def encrypt_secret(value: str, settings: Settings) -> str:
    return make_fernet(settings).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(encrypted: str, settings: Settings) -> str:
    try:
        return make_fernet(settings).decrypt(encrypted.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("cannot decrypt secret (bad key or corrupted value)") from exc
