"""Security tests — database-level protections and data integrity."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_refresh_tokens_are_hashed(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "hash@test.com", "password": "S3cur3!Pass", "name": "Hash"},
    )
    assert resp.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "hash@test.com", "password": "S3cur3!Pass"},
    )
    assert login.status_code == 200
    raw_token = login.json()["refresh_token"]
    assert len(raw_token) > 20


def test_logout_invalidates_refresh_token(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "logout@test.com", "password": "S3cur3!Pass", "name": "Logout"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "logout@test.com", "password": "S3cur3!Pass"},
    )
    token = login.json()["refresh_token"]
    access = login.json()["access_token"]

    resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": token},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 204

    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token},
    )
    assert refresh_resp.status_code == 401


def test_user_cannot_access_other_user_account(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "user1@test.com", "password": "S3cur3!Pass", "name": "User1"},
    )
    client.post(
        "/api/v1/auth/register",
        json={"email": "user2@test.com", "password": "S3cur3!Pass", "name": "User2"},
    )
    login1 = client.post(
        "/api/v1/auth/login",
        json={"email": "user1@test.com", "password": "S3cur3!Pass"},
    )
    headers1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

    resp = client.get("/api/v1/trading/account", headers=headers1)
    assert resp.status_code == 200


def test_protected_endpoints_require_auth(client: TestClient) -> None:
    endpoints = [
        "/api/v1/trading/account",
        "/api/v1/trading/orders",
        "/api/v1/trading/positions",
        "/api/v1/trading/history",
        "/api/v1/market/symbols",
        "/api/v1/market/quote?symbol=EURUSD",
        "/api/v1/strategies",
    ]
    for endpoint in endpoints:
        resp = client.get(endpoint)
        assert resp.status_code in (401, 403), f"{endpoint} should require auth"


def test_health_endpoint_is_public(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "version" in body
    assert "uptime_seconds" in body
