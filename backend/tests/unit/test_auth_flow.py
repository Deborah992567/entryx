"""Integration tests for complete auth flow: register → login → me → refresh → logout."""

from __future__ import annotations

from app.main import app
from starlette.testclient import TestClient


def test_full_auth_flow() -> None:
    client = TestClient(app)

    import uuid
    email = f"integration{uuid.uuid4().hex[:8]}@test.com"

    # 1. Register
    r = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Secure1234",
        "name": "Integration User",
    })
    assert r.status_code == 201
    user = r.json()
    assert user["email"] == email
    assert user["role"] == "user"

    # 2. Login
    r = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Secure1234",
    })
    assert r.status_code == 200
    tokens = r.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] > 0
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 3. Get profile
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == user["id"]

    # 4. Refresh token
    r = client.post("/api/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"],
    })
    assert r.status_code == 200
    new_tokens = r.json()
    assert new_tokens["access_token"] != tokens["refresh_token"]
    new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}

    # 5. Profile works with new token
    r = client.get("/api/v1/auth/me", headers=new_headers)
    assert r.status_code == 200

    # 6. Old token still works (not revoked)
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200

    # 7. Logout
    r = client.post("/api/v1/auth/logout", json={
        "refresh_token": new_tokens["refresh_token"],
    }, headers=new_headers)
    assert r.status_code == 204

    # 8. Refresh token is now invalid
    r = client.post("/api/v1/auth/refresh", json={
        "refresh_token": new_tokens["refresh_token"],
    })
    assert r.status_code == 401


def test_register_duplicate_email_conflict() -> None:
    client = TestClient(app)
    import uuid
    email = f"dup{uuid.uuid4().hex[:8]}@test.com"
    payload = {"email": email, "password": "Dup123456", "name": "Dup"}

    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201

    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]["message"]


def test_login_wrong_password() -> None:
    client = TestClient(app)
    import uuid
    email = f"wrongpw{uuid.uuid4().hex[:8]}@test.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "Correct123", "name": "Test",
    })

    r = client.post("/api/v1/auth/login", json={
        "email": email, "password": "WrongPassword1",
    })
    assert r.status_code == 401
    assert "invalid credentials" in r.json()["detail"]["message"]
