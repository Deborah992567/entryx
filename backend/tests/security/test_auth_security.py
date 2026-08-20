"""Security tests — password strength, token tampering, credential leakage."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_rejects_short_password(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "Ab1!", "name": "X"},
    )
    assert resp.status_code in (400, 422)


def test_rejects_letters_only_password(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "abcdefgh", "name": "X"},
    )
    assert resp.status_code in (400, 422)


def test_rejects_digits_only_password(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "12345678", "name": "X"},
    )
    assert resp.status_code in (400, 422)


def test_valid_password_accepted(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "valid@test.com", "password": "S3cur3!Pass", "name": "Valid"},
    )
    assert resp.status_code == 201


def test_login_rejects_wrong_password(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "wrong@test.com", "password": "S3cur3!Pass", "name": "W"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@test.com", "password": "WrongPass1!"},
    )
    assert resp.status_code == 401


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    payload = {"email": "dup@test.com", "password": "S3cur3!Pass", "name": "Dup"}
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201
    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409


def test_password_not_returned_in_register_response(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "noleak@test.com", "password": "S3cur3!Pass", "name": "NoLeak"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "password" not in body
    assert "password_hash" not in body


def test_refresh_token_required_for_refresh(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/refresh", json={})
    assert resp.status_code in (400, 422)


def test_invalid_refresh_token_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "totally-invalid-token-value-here"},
    )
    assert resp.status_code in (401, 400)


def test_truncated_token_rejected(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "trunc@test.com", "password": "S3cur3!Pass", "name": "T"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "trunc@test.com", "password": "S3cur3!Pass"},
    )
    token = login.json()["access_token"]
    truncated = token[: len(token) // 2]
    resp = client.get(
        "/api/v1/system/status",
        headers={"Authorization": f"Bearer {truncated}"},
    )
    assert resp.status_code in (401, 403)
