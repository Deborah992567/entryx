"""Paper trading API tests (Phase 2)."""

from __future__ import annotations

import pytest
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


def test_place_stop_limit_pending(client: TestClient, auth_headers: dict) -> None:
    quote = client.get("/api/v1/market/quote?symbol=EURUSD", headers=auth_headers).json()
    stop = round(quote["ask"] + 1.0, 5)
    resp = client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={
            "symbol": "EURUSD",
            "side": "buy",
            "type": "stop_limit",
            "volume": 0.5,
            "price": stop,
            "limit_price": round(stop + 0.2, 5),
            "expiry": "2099-01-01T00:00:00Z",
            "magic": 7,
            "comment": "l1",
        },
    )
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["state"] == "pending"
    assert order["type"] == "stop_limit"
    assert order["limit_price"] == pytest.approx(round(stop + 0.2, 5))
    assert order["expiry"] is not None
    assert order["magic"] == 7
    assert order["comment"] == "l1"

    orders = client.get("/api/v1/trading/orders", headers=auth_headers).json()
    assert any(o["id"] == order["id"] for o in orders)


def test_expiry_in_past_returns_400(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "EURUSD", "side": "buy", "type": "limit", "volume": 0.5, "price": 1.0, "expiry": "2020-01-01T00:00:00Z"},
    )
    assert resp.status_code == 400


def test_invalid_sl_tp_returns_400(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "EURUSD", "side": "buy", "type": "market", "volume": 1, "sl": 100_000},
    )
    assert resp.status_code == 400


def test_invalid_stop_limit_returns_400(client: TestClient, auth_headers: dict) -> None:
    quote = client.get("/api/v1/market/quote?symbol=EURUSD", headers=auth_headers).json()
    stop = round(quote["ask"] + 1.0, 5)
    resp = client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "EURUSD", "side": "buy", "type": "stop_limit", "volume": 0.5, "price": stop, "limit_price": round(stop - 0.1, 5)},
    )
    assert resp.status_code == 400


def test_partial_close_via_api(client: TestClient, auth_headers: dict) -> None:
    client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "EURUSD", "side": "buy", "type": "market", "volume": 2.0},
    )
    position_id = client.get("/api/v1/trading/positions", headers=auth_headers).json()[0]["id"]
    resp = client.post(
        f"/api/v1/trading/positions/{position_id}/close",
        headers=auth_headers,
        json={"volume": 0.5},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["volume"] == 0.5

    positions = client.get("/api/v1/trading/positions", headers=auth_headers).json()
    assert len(positions) == 1
    assert positions[0]["id"] == position_id
    assert positions[0]["volume"] == pytest.approx(1.5)
    assert len(client.get("/api/v1/trading/history", headers=auth_headers).json()) == 1


def test_modify_position_via_api(client: TestClient, auth_headers: dict) -> None:
    client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "EURUSD", "side": "buy", "type": "market", "volume": 1.0},
    )
    position_id = client.get("/api/v1/trading/positions", headers=auth_headers).json()[0]["id"]
    quote = client.get("/api/v1/market/quote?symbol=EURUSD", headers=auth_headers).json()
    sl = round(quote["bid"] - 0.01, 5)
    tp = round(quote["bid"] + 0.01, 5)
    resp = client.patch(
        f"/api/v1/trading/positions/{position_id}",
        headers=auth_headers,
        json={"sl": sl, "tp": tp, "trail": 0.005},
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["sl"] == pytest.approx(sl)
    assert updated["tp"] == pytest.approx(tp)
    assert updated["trail"] == pytest.approx(0.005)


def test_modify_position_invalid_returns_400(client: TestClient, auth_headers: dict) -> None:
    client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "EURUSD", "side": "buy", "type": "market", "volume": 1.0},
    )
    position_id = client.get("/api/v1/trading/positions", headers=auth_headers).json()[0]["id"]
    quote = client.get("/api/v1/market/quote?symbol=EURUSD", headers=auth_headers).json()
    bad_sl = round(quote["bid"] + 1.0, 5)
    resp = client.patch(f"/api/v1/trading/positions/{position_id}", headers=auth_headers, json={"sl": bad_sl})
    assert resp.status_code == 400


def test_account_exposes_commission_swap_exposure(client: TestClient, auth_headers: dict) -> None:
    account = client.get("/api/v1/trading/account", headers=auth_headers).json()
    assert account["commission"] == 0
    assert account["swap"] == 0
    assert account["exposure"] == 0

    client.post(
        "/api/v1/trading/orders",
        headers=auth_headers,
        json={"symbol": "EURUSD", "side": "buy", "type": "market", "volume": 1.0},
    )
    account = client.get("/api/v1/trading/account", headers=auth_headers).json()
    assert account["commission"] > 0
    assert account["exposure"] > 0
    assert account["margin_used"] > 0
    assert account["free_margin"] < account["equity"]
