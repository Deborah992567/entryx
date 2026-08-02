"""Deterministic tests for the auth API."""

from __future__ import annotations


def test_register_creates_user(client, user_payload):
    resp = client.post("/api/v1/auth/register", json=user_payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == user_payload["email"]
    assert "password" not in body
    assert "password_hash" not in body


def test_register_rejects_duplicate_email(client, registered_user, user_payload):
    resp = client.post("/api/v1/auth/register", json=user_payload)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ERR_CONFLICT"


def test_register_rejects_weak_password(client, user_payload):
    weak = {**user_payload, "password": "short"}
    resp = client.post("/api/v1/auth/register", json=weak)
    assert resp.status_code == 422


def test_register_rejects_letters_only_password(client, user_payload):
    weak = {**user_payload, "password": "onlyletters"}
    resp = client.post("/api/v1/auth/register", json=weak)
    assert resp.status_code == 422


def test_login_returns_tokens(client, registered_user, user_payload):
    resp = client.post("/api/v1/auth/login", json=user_payload)
    assert resp.status_code == 200
    tokens = resp.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 15 * 60


def test_login_rejects_bad_password(client, registered_user, user_payload):
    resp = client.post("/api/v1/auth/login", json={**user_payload, "password": "wrongpass"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "ERR_UNAUTHORIZED"


def test_login_rejects_unknown_email(client, user_payload):
    resp = client.post("/api/v1/auth/login", json=user_payload)
    assert resp.status_code == 401


def test_me_requires_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_user(client, auth_headers, user_payload):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == user_payload["email"]


def test_refresh_rotates_tokens(client, registered_user, user_payload):
    login = client.post("/api/v1/auth/login", json=user_payload).json()
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert resp.status_code == 200
    pair = resp.json()
    assert pair["access_token"]
    assert pair["refresh_token"] != login["refresh_token"]


def test_refresh_token_is_single_use(client, registered_user, user_payload):
    login = client.post("/api/v1/auth/login", json=user_payload).json()
    refresh_token = login["refresh_token"]
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}).status_code == 200
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401


def test_refresh_rejects_garbage(client, registered_user):
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
    assert resp.status_code == 401


def test_logout_revokes_refresh(client, registered_user, user_payload):
    login = client.post("/api/v1/auth/login", json=user_payload).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    resp = client.post("/api/v1/auth/logout", json={"refresh_token": login["refresh_token"]}, headers=headers)
    assert resp.status_code == 204
    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert refresh.status_code == 401


def test_audit_logs_written(client, auth_headers, user_payload):
    from app.db import models as m

    from tests.conftest import TEST_SESSION

    with TEST_SESSION() as session:
        actions = session.query(m.AuditLog).all()
    assert {a.action for a in actions} >= {"auth.register", "auth.login"}
    assert all("password" not in str(a.detail_json).lower() for a in actions)


def test_rate_limit(client, registered_user, user_payload):
    resp = None
    for _ in range(12):
        resp = client.post("/api/v1/auth/login", json={**user_payload, "password": "wrongpass"})
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "ERR_RATE_LIMITED"
