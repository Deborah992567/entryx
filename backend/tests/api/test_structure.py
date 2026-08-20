"""Market structure API tests (Phase 6 line 1)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_structure_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/structure?symbol=EURUSD")
    assert resp.status_code == 401


def test_structure_returns_all_detectors(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/structure?symbol=XAUUSD&tf=H1&limit=200", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "XAUUSD"
    assert body["timeframe"] == "H1"
    assert body["candles"] == 200
    assert body["left"] == 5 and body["right"] == 2
    assert body["swings"]
    for key in ("bos", "choch", "regimes", "breakouts", "retests"):
        assert key in body
        for obj in body[key]:
            assert {"kind", "bar_index", "ts", "price", "timeframe", "direction", "status"} <= set(
                obj
            )


def test_structure_honours_swing_params(client: TestClient, auth_headers: dict) -> None:
    resp = client.get(
        "/api/v1/structure?symbol=EURUSD&tf=H1&limit=100&left=3&right=1", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["left"] == 3 and body["right"] == 1
    assert all(o["bar_index"] >= 3 for o in body["swings"])


def test_structure_unknown_symbol(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/structure?symbol=NOPE", headers=auth_headers)
    assert resp.status_code == 404


def test_structure_bad_timeframe(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/structure?symbol=EURUSD&tf=XX", headers=auth_headers)
    assert resp.status_code == 422
