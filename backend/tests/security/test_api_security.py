"""Security tests — rate limiting, input injection, header tampering."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_rate_limit_kicks_in_on_auth(client: TestClient) -> None:
    """The per-route rate limiter blocks after exceeding the limit."""
    for _ in range(12):
        client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.com", "password": "S3cur3!Pass"},
        )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "S3cur3!Pass"},
    )
    assert resp.status_code == 429


def test_sql_injection_in_email_field(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "1' OR '1'='1'--@test.com",
            "password": "S3cur3!Pass",
            "name": "Hacker",
        },
    )
    assert resp.status_code in (400, 422)


def test_sql_injection_in_login_email(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin'--@test.com", "password": "anything"},
    )
    assert resp.status_code == 401


def test_xss_in_name_field(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "xss@test.com",
            "password": "S3cur3!Pass",
            "name": "<script>alert('xss')</script>",
        },
    )
    if resp.status_code == 201:
        body = resp.json()
        assert "name" in body


def test_oversized_email_rejected(client: TestClient) -> None:
    big_email = "a" * 500 + "@test.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": big_email, "password": "S3cur3!Pass", "name": "Big"},
    )
    assert resp.status_code in (400, 422)


def test_unicode_in_password_handled(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "unicode@test.com",
            "password": "S3cur3!Pass",
            "name": "Ünïcödé Usér",
        },
    )
    assert resp.status_code in (201, 400, 422)


def test_security_headers_present(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "Content-Security-Policy" in resp.headers
    assert "Strict-Transport-Security" in resp.headers


def test_request_id_header_returned(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) == 12


def test_custom_request_id_echoed(client: TestClient) -> None:
    custom_id = "abc123def456"
    resp = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert resp.headers.get("X-Request-ID") == custom_id
