"""API tests for chart drawing persistence."""

from __future__ import annotations

DRAWINGS_URL = "/api/v1/workspace/drawings"

TRENDLINE = {
    "kind": "trendLine",
    "points_json": {
        "type": "trendLine",
        "id": 1,
        "color": 3866623,
        "p1": {"bar": 10.0, "price": 100.0},
        "p2": {"bar": 90.0, "price": 110.0},
    },
}

FIB = {
    "kind": "fibonacci",
    "points_json": {
        "type": "fibonacci",
        "id": 2,
        "color": 3866623,
        "p1": {"bar": 10.0, "price": 110.0},
        "p2": {"bar": 90.0, "price": 100.0},
    },
}


def test_drawings_require_auth(client):
    assert client.get(DRAWINGS_URL, params={"symbol": "XAUUSD", "timeframe": "H1"}).status_code == 401
    assert client.put(DRAWINGS_URL, json={"symbol": "XAUUSD", "timeframe": "H1", "drawings": []}).status_code == 401


def test_list_empty(client, auth_headers):
    resp = client.get(DRAWINGS_URL, params={"symbol": "XAUUSD", "timeframe": "H1"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_sync_then_list(client, auth_headers):
    body = {"symbol": "XAUUSD", "timeframe": "H1", "drawings": [TRENDLINE, FIB]}
    created = client.put(DRAWINGS_URL, json=body, headers=auth_headers)
    assert created.status_code == 200
    assert len(created.json()) == 2

    listed = client.get(DRAWINGS_URL, params={"symbol": "XAUUSD", "timeframe": "H1"}, headers=auth_headers).json()
    assert [d["kind"] for d in listed] == ["trendLine", "fibonacci"]
    assert listed[0]["points_json"]["p1"] == {"bar": 10.0, "price": 100.0}


def test_sync_is_scoped_to_symbol_and_timeframe(client, auth_headers):
    body = {"symbol": "XAUUSD", "timeframe": "H1", "drawings": [TRENDLINE]}
    client.put(DRAWINGS_URL, json=body, headers=auth_headers)
    other = client.get(
        DRAWINGS_URL, params={"symbol": "EURUSD", "timeframe": "H1"}, headers=auth_headers
    ).json()
    other_tf = client.get(
        DRAWINGS_URL, params={"symbol": "XAUUSD", "timeframe": "M15"}, headers=auth_headers
    ).json()
    assert other == []
    assert other_tf == []


def test_sync_replaces_previous_set(client, auth_headers):
    body = {"symbol": "XAUUSD", "timeframe": "H1", "drawings": [TRENDLINE, FIB]}
    client.put(DRAWINGS_URL, json=body, headers=auth_headers)
    client.put(DRAWINGS_URL, json={"symbol": "XAUUSD", "timeframe": "H1", "drawings": [FIB]}, headers=auth_headers)
    listed = client.get(DRAWINGS_URL, params={"symbol": "XAUUSD", "timeframe": "H1"}, headers=auth_headers).json()
    assert [d["kind"] for d in listed] == ["fibonacci"]


def test_drawings_are_user_scoped(client, auth_headers, user_payload):
    client.put(
        DRAWINGS_URL,
        json={"symbol": "XAUUSD", "timeframe": "H1", "drawings": [TRENDLINE]},
        headers=auth_headers,
    )
    other = {**user_payload, "email": "other@entryx.com"}
    client.post("/api/v1/auth/register", json=other)
    login = client.post("/api/v1/auth/login", json=other).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    resp = client.get(DRAWINGS_URL, params={"symbol": "XAUUSD", "timeframe": "H1"}, headers=headers)
    assert resp.json() == []


def test_clear_drawings(client, auth_headers):
    client.put(
        DRAWINGS_URL,
        json={"symbol": "XAUUSD", "timeframe": "H1", "drawings": [TRENDLINE]},
        headers=auth_headers,
    )
    resp = client.delete(DRAWINGS_URL, params={"symbol": "XAUUSD", "timeframe": "H1"}, headers=auth_headers)
    assert resp.status_code == 204
    assert client.get(
        DRAWINGS_URL, params={"symbol": "XAUUSD", "timeframe": "H1"}, headers=auth_headers
    ).json() == []


def test_clear_is_scoped(client, auth_headers):
    client.put(
        DRAWINGS_URL,
        json={"symbol": "XAUUSD", "timeframe": "H1", "drawings": [TRENDLINE]},
        headers=auth_headers,
    )
    client.delete(DRAWINGS_URL, params={"symbol": "EURUSD", "timeframe": "H1"}, headers=auth_headers)
    listed = client.get(
        DRAWINGS_URL, params={"symbol": "XAUUSD", "timeframe": "H1"}, headers=auth_headers
    ).json()
    assert len(listed) == 1
