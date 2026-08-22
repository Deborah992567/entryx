"""Tests for trading API endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app
from app.middleware import RateLimitMiddleware


def _auth_headers() -> dict:
    from app.core import security
    from app.core.config import get_settings
    token = security.create_access_token("1", get_settings())
    return {"Authorization": f"Bearer {token}"}


def test_account_summary() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/trading/account", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert "balance" in data
    assert "equity" in data
    assert "currency" in data


def test_list_orders_empty() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/trading/orders", headers=_auth_headers())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_positions_empty() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/trading/positions", headers=_auth_headers())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_trades_empty() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/trading/history", headers=_auth_headers())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_and_fill_order() -> None:
    RateLimitMiddleware.reset()
    client = TestClient(app)
    r = client.post("/api/v1/trading/orders", headers=_auth_headers(), json={
        "symbol": "EURUSD", "side": "buy", "type": "market", "volume": 0.1,
    })
    assert r.status_code == 201
    order = r.json()
    assert order["symbol"] == "EURUSD"
    assert order["side"] == "buy"
    assert order["state"] == "filled"

    r = client.get("/api/v1/trading/positions", headers=_auth_headers())
    assert r.status_code == 200
    positions = r.json()
    assert len(positions) >= 1


def test_trading_unauthenticated() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/trading/account")
    assert r.status_code == 401


def test_risk_assessment() -> None:
    RateLimitMiddleware.reset()
    client = TestClient(app)
    r = client.post("/api/v1/trading/risk/assess", headers=_auth_headers(), json={
        "symbol": "EURUSD", "equity": 100000, "risk_pct": 1.0,
        "entry": 1.1, "sl": 1.09, "tp": 1.12,
    })
    assert r.status_code == 200
    data = r.json()
    assert "lots" in data
    assert "rr" in data
    assert "margin_required" in data
