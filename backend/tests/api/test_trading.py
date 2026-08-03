"""Paper trading API tests (Phase 2)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_account_defaults(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/trading/account", headers=auth_headers)
    assert resp.status_code == 200
    account = resp.json()
    assert account["number"] == "0001-PAPER"
    assert account["balance"] == 100_000
    assert account["equity"] == 100_000
    assert account["margin_used"] == 0
    assert account["free_margin"] == 100_000
    assert account["margin_level"] == 0


def test_place_market_order_and_account_changes(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "EURUSD", "side": "buy", "type": "market", "volume": 0.5},
    )
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["state"] == "filled"
    assert order["filled_price"] is not None

    positions = client.get("/api/v1/trading/positions", headers=auth_headers).json()
    assert len(positions) == 1
    assert positions[0]["id"].startswith("p-")

    account = client.get("/api/v1/trading/account", headers=auth_headers).json()
    assert account["margin_used"] > 0
    assert account["balance"] < 100_000  # commission deducted


def test_rejected_order_when_no_margin(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "XAUUSD", "side": "buy", "type": "market", "volume": 1_000_000},
    )
    assert resp.status_code == 201
    assert resp.json()["state"] == "rejected"


def test_invalid_side_returns_400(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "EURUSD", "side": "hold", "type": "market", "volume": 1},
    )
    assert resp.status_code == 400


def test_pending_order_lifecycle(client: TestClient, auth_headers: dict) -> None:
    quote = client.get("/api/v1/market/quote?symbol=GBPUSD", headers=auth_headers).json()
    far = round(quote["ask"] - 1.0, 5)
    created = client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "GBPUSD", "side": "buy", "type": "limit", "volume": 0.2, "price": far},
    )
    assert created.status_code == 201
    order_id = created.json()["id"]
    assert created.json()["state"] == "pending"

    orders = client.get("/api/v1/trading/orders", headers=auth_headers).json()
    assert any(o["id"] == order_id for o in orders)

    cancelled = client.delete(f"/api/v1/trading/orders/{order_id}", headers=auth_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"


def test_close_position_records_history(client: TestClient, auth_headers: dict) -> None:
    client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "EURUSD", "side": "buy", "type": "market", "volume": 1.0},
    )
    position_id = client.get("/api/v1/trading/positions", headers=auth_headers).json()[0]["id"]
    closed = client.delete(f"/api/v1/trading/positions/{position_id}", headers=auth_headers)
    assert closed.status_code == 200
    trade = closed.json()
    assert trade["net_pnl"] < trade["gross_pnl"]  # both open and close commission
    assert trade["commission"] > 0

    history = client.get("/api/v1/trading/history", headers=auth_headers).json()
    assert len(history) == 1

    positions = client.get("/api/v1/trading/positions", headers=auth_headers).json()
    assert positions == []


def test_close_unknown_position_returns_400(client: TestClient, auth_headers: dict) -> None:
    resp = client.delete("/api/v1/trading/positions/p-nope", headers=auth_headers)
    assert resp.status_code == 400
