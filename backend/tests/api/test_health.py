"""Health endpoint tests."""

from __future__ import annotations


def test_health_public(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"  # AI still pending (Phase 7)
    assert body["app"] == "EntryX"
    assert "database" in body["components"]
    assert body["components"]["market_data"]["status"] == "ok"
    assert body["components"]["broker"]["status"] == "ok"
    assert body["components"]["ai"]["status"] == "degraded"


def test_system_status_requires_auth(client):
    assert client.get("/api/v1/system/status").status_code == 401


def test_system_status_authenticated(client, auth_headers):
    resp = client.get("/api/v1/system/status", headers=auth_headers)
    assert resp.status_code == 200
    assert "ws" in resp.json()


def test_root_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["app"] == "EntryX"
