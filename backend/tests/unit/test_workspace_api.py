"""Tests for workspace layout CRUD API."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app
from app.middleware import RateLimitMiddleware


def _auth_headers() -> dict:
    from app.core import security
    from app.core.config import get_settings
    token = security.create_access_token("1", get_settings())
    return {"Authorization": f"Bearer {token}"}


def test_list_layouts_empty() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/workspace/layouts", headers=_auth_headers())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_layout() -> None:
    RateLimitMiddleware.reset()
    client = TestClient(app)
    r = client.post("/api/v1/workspace/layouts", headers=_auth_headers(), json={
        "name": "My Layout",
        "layout_json": {"panels": [{"type": "chart", "w": 8, "h": 6}]},
        "is_default": True,
    })
    assert r.status_code == 201
    layout = r.json()
    assert layout["name"] == "My Layout"
    assert layout["is_default"] is True
    assert "id" in layout


def test_create_and_list_layouts() -> None:
    RateLimitMiddleware.reset()
    client = TestClient(app)
    client.post("/api/v1/workspace/layouts", headers=_auth_headers(), json={
        "name": "Layout A", "layout_json": {},
    })
    client.post("/api/v1/workspace/layouts", headers=_auth_headers(), json={
        "name": "Layout B", "layout_json": {},
    })
    r = client.get("/api/v1/workspace/layouts", headers=_auth_headers())
    assert r.status_code == 200
    layouts = r.json()
    assert len(layouts) >= 2


def test_update_layout() -> None:
    RateLimitMiddleware.reset()
    client = TestClient(app)
    r = client.post("/api/v1/workspace/layouts", headers=_auth_headers(), json={
        "name": "Original", "layout_json": {},
    })
    layout_id = r.json()["id"]
    r = client.put(f"/api/v1/workspace/layouts/{layout_id}", headers=_auth_headers(), json={
        "name": "Updated",
    })
    assert r.status_code == 200
    assert r.json()["name"] == "Updated"


def test_delete_layout() -> None:
    RateLimitMiddleware.reset()
    client = TestClient(app)
    r = client.post("/api/v1/workspace/layouts", headers=_auth_headers(), json={
        "name": "To Delete", "layout_json": {},
    })
    layout_id = r.json()["id"]
    r = client.delete(f"/api/v1/workspace/layouts/{layout_id}", headers=_auth_headers())
    assert r.status_code == 204


def test_workspace_unauthenticated() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/workspace/layouts")
    assert r.status_code == 401
