"""API tests for workspace layout persistence."""

from __future__ import annotations

LAYOUT = {
    "name": "default",
    "layout_json": {
        "nodes": [
            {"id": "chart1", "type": "chart", "x": 0, "y": 0, "w": 3, "h": 2},
            {"id": "watch", "type": "marketwatch", "x": 3, "y": 0, "w": 1, "h": 2},
        ]
    },
    "is_default": True,
}


def test_list_empty(client, auth_headers):
    resp = client.get("/api/v1/workspace/layouts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_layout(client, auth_headers):
    resp = client.post("/api/v1/workspace/layouts", json=LAYOUT, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "default"
    assert body["is_default"] is True
    assert body["layout_json"]["nodes"][0]["type"] == "chart"


def test_layouts_are_user_scoped(client, auth_headers, user_payload):
    client.post("/api/v1/workspace/layouts", json=LAYOUT, headers=auth_headers)
    other = {**user_payload, "email": "other@entryx.com"}
    client.post("/api/v1/auth/register", json=other)
    login = client.post("/api/v1/auth/login", json=other).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    resp = client.get("/api/v1/workspace/layouts", headers=headers)
    assert resp.json() == []


def test_update_layout(client, auth_headers):
    created = client.post("/api/v1/workspace/layouts", json=LAYOUT, headers=auth_headers).json()
    resp = client.put(
        f"/api/v1/workspace/layouts/{created['id']}",
        json={"name": "renamed", "layout_json": {"nodes": []}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "renamed"
    assert body["layout_json"] == {"nodes": []}


def test_default_flag_is_exclusive(client, auth_headers):
    a = client.post(
        "/api/v1/workspace/layouts",
        json={**LAYOUT, "name": "a", "is_default": True},
        headers=auth_headers,
    ).json()
    b = client.post(
        "/api/v1/workspace/layouts",
        json={**LAYOUT, "name": "b", "is_default": True},
        headers=auth_headers,
    ).json()
    resp = client.get("/api/v1/workspace/layouts", headers=auth_headers).json()
    default_flags = [layout["is_default"] for layout in resp]
    assert default_flags.count(True) == 1
    assert a["id"] != b["id"]


def test_delete_layout(client, auth_headers):
    created = client.post("/api/v1/workspace/layouts", json=LAYOUT, headers=auth_headers).json()
    resp = client.delete(f"/api/v1/workspace/layouts/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get("/api/v1/workspace/layouts", headers=auth_headers).json() == []


def test_cannot_touch_other_users_layout(client, auth_headers, user_payload):
    created = client.post("/api/v1/workspace/layouts", json=LAYOUT, headers=auth_headers).json()
    other = {**user_payload, "email": "intruder@entryx.com"}
    client.post("/api/v1/auth/register", json=other)
    login = client.post("/api/v1/auth/login", json=other).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    resp = client.delete(f"/api/v1/workspace/layouts/{created['id']}", headers=headers)
    assert resp.status_code == 404


def test_update_missing_layout_404(client, auth_headers):
    resp = client.put("/api/v1/workspace/layouts/9999", json={"name": "x"}, headers=auth_headers)
    assert resp.status_code == 404


def test_workspace_requires_auth(client):
    assert client.get("/api/v1/workspace/layouts").status_code == 401
