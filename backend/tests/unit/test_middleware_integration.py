"""Tests for CORS configuration and middleware integration."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app


def test_cors_preflight_allowed() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert resp.status_code in (200, 405)
    assert "access-control-allow-origin" in resp.headers


def test_security_headers_present() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("x-api-version") == "1"


def test_request_id_header() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/health")
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) > 0


def test_custom_request_id_echoed() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/health", headers={"X-Request-ID": "my-trace-123"})
    assert resp.headers.get("x-request-id") == "my-trace-123"
