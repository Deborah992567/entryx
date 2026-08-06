"""Strategy framework API tests (Phase 5 line 1)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_strategies_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/strategies")
    assert resp.status_code == 401


def test_list_strategies_catalog(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/strategies", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    names = {item["name"] for item in resp.json()}
    assert "sma_cross" in names


def test_start_and_stop_instance(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/strategies/sma_cross/start",
        headers=auth_headers,
        json={"symbol": "EURUSD", "params": {"fast": 3, "slow": 5}},
    )
    assert resp.status_code == 201, resp.text
    instance = resp.json()
    assert instance["status"] == "running"
    assert instance["strategy"] == "sma_cross"
    assert instance["symbol"] == "EURUSD"
    assert instance["magic"] >= 10_000

    instances = client.get("/api/v1/strategies/instances", headers=auth_headers).json()
    assert any(i["instance_id"] == instance["instance_id"] for i in instances)

    stopped = client.post(
        f"/api/v1/strategies/instances/{instance['instance_id']}/stop",
        headers=auth_headers,
    )
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["status"] == "stopped"

    remaining = client.get("/api/v1/strategies/instances", headers=auth_headers).json()
    assert all(i["instance_id"] != instance["instance_id"] for i in remaining)


def test_start_unknown_strategy_returns_404(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/strategies/does_not_exist/start",
        headers=auth_headers,
        json={"symbol": "EURUSD"},
    )
    assert resp.status_code == 404


def test_start_invalid_params_returns_400(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/strategies/sma_cross/start",
        headers=auth_headers,
        json={"symbol": "EURUSD", "params": {"fast": 30, "slow": 10}},
    )
    assert resp.status_code == 400


def test_stop_unknown_instance_returns_404(client: TestClient, auth_headers: dict) -> None:
    resp = client.post("/api/v1/strategies/instances/st-nope/stop", headers=auth_headers)
    assert resp.status_code == 404
