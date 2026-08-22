"""Tests for application root and version endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app


def test_root_returns_app_info() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "app" in data
    assert "docs" in data
    assert "health" in data


def test_version_returns_version() -> None:
    client = TestClient(app)
    resp = client.get("/version")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert data["version"] == "0.1.0"
    assert "app" in data


def test_health_returns_ok() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "components" in data
    assert "uptime_seconds" in data


def test_docs_accessible() -> None:
    client = TestClient(app)
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_redoc_accessible() -> None:
    client = TestClient(app)
    resp = client.get("/redoc")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_openapi_json_accessible() -> None:
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "openapi" in data
    assert "paths" in data


def test_404_returns_json_envelope() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data
