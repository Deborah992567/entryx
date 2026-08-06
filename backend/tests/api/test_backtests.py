"""Backtest API tests (Phase 5 line 2)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_backtest_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/backtests",
        json={"strategy": "sma_cross", "symbol": "EURUSD", "candle_count": 10},
    )
    assert resp.status_code == 401


def test_create_backtest_returns_result(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/backtests",
        headers=auth_headers,
        json={
            "strategy": "sma_cross",
            "symbol": "EURUSD",
            "timeframe": "H1",
            "candle_count": 10,
            "config": {"initial_balance": 10_000, "spread_mult": 0.0},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["strategy"] == "sma_cross"
    assert body["symbol"] == "EURUSD"
    assert body["status"] == "stopped"
    assert body["metrics"]["start_balance"] == 10_000
    assert body["metrics"]["total_trades"] >= 0
    assert len(body["equity_curve"]) == 10
    assert isinstance(body["config"], dict)
    assert body["config"]["spread_mult"] == 0.0


def test_get_backtest_returns_saved_run(client: TestClient, auth_headers: dict) -> None:
    created = client.post(
        "/api/v1/backtests",
        headers=auth_headers,
        json={"strategy": "sma_cross", "symbol": "EURUSD", "candle_count": 10},
    )
    run_id = created.json()["id"]

    fetched = client.get(f"/api/v1/backtests/{run_id}", headers=auth_headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == run_id


def test_get_unknown_backtest_returns_404(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/backtests/bt-nope", headers=auth_headers)
    assert resp.status_code == 404


def test_unknown_strategy_returns_404(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/backtests",
        headers=auth_headers,
        json={"strategy": "does_not_exist", "symbol": "EURUSD", "candle_count": 10},
    )
    assert resp.status_code == 404


def test_invalid_config_returns_400(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/backtests",
        headers=auth_headers,
        json={"strategy": "sma_cross", "symbol": "EURUSD", "candle_count": 10, "config": {"initial_balance": 1}},
    )
    assert resp.status_code == 422


def test_other_users_cannot_read_others_runs(client: TestClient, auth_headers: dict) -> None:
    created = client.post(
        "/api/v1/backtests",
        headers=auth_headers,
        json={"strategy": "sma_cross", "symbol": "EURUSD", "candle_count": 10},
    )
    run_id = created.json()["id"]

    other = client.post(
        "/api/v1/auth/register",
        json={"email": "other@entryx.com", "password": "sup3rSecret", "name": "Other"},
    )
    assert other.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": "other@entryx.com", "password": "sup3rSecret"})
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.get(f"/api/v1/backtests/{run_id}", headers=other_headers)
    assert resp.status_code == 404
