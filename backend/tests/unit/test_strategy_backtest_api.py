"""Tests for strategy and backtest API endpoints."""

from __future__ import annotations

from app.main import app
from app.middleware import RateLimitMiddleware
from starlette.testclient import TestClient


def _auth_headers() -> dict:
    from app.core import security
    from app.core.config import get_settings
    token = security.create_access_token("1", get_settings())
    return {"Authorization": f"Bearer {token}"}


def test_list_strategies() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/strategies", headers=_auth_headers())
    assert r.status_code == 200
    strategies = r.json()
    assert isinstance(strategies, list)
    assert len(strategies) > 0
    assert all("name" in s for s in strategies)


def test_list_instances_empty() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/strategies/instances", headers=_auth_headers())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_strategies_unauthenticated() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/strategies")
    assert r.status_code == 401


def test_start_invalid_strategy() -> None:
    RateLimitMiddleware.reset()
    client = TestClient(app)
    r = client.post("/api/v1/strategies/nonexistent/start", headers=_auth_headers(), json={
        "symbol": "EURUSD", "timeframe": "H1", "candles": 200, "params": {},
    })
    assert r.status_code == 404


def test_run_backtest() -> None:
    RateLimitMiddleware.reset()
    client = TestClient(app)
    r = client.post("/api/v1/backtests", headers=_auth_headers(), json={
        "strategy": "sma_cross",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "candle_count": 500,
        "params": {"fast_period": 10, "slow_period": 30},
        "config": {
            "initial_balance": 100000,
            "leverage": 100,
            "commission_bps": 10,
            "slippage_points": 2,
            "spread_mult": 1.0,
            "swap_enabled": False,
            "margin_enabled": True,
        },
    })
    assert r.status_code == 201
    result = r.json()
    assert "id" in result
    assert "metrics" in result
    assert "trades" in result


def test_run_backtest_invalid_strategy() -> None:
    RateLimitMiddleware.reset()
    client = TestClient(app)
    r = client.post("/api/v1/backtests", headers=_auth_headers(), json={
        "strategy": "nonexistent_strategy",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "candle_count": 500,
        "params": {},
        "config": {
            "initial_balance": 100000, "leverage": 100,
            "commission_bps": 10, "slippage_points": 2,
            "spread_mult": 1.0, "swap_enabled": False, "margin_enabled": True,
        },
    })
    assert r.status_code in (400, 404)


def test_backtest_unauthenticated() -> None:
    client = TestClient(app)
    r = client.post("/api/v1/backtests", json={
        "strategy": "ma_cross",
        "symbol": "EURUSD", "timeframe": "H1",
        "candle_count": 100, "params": {},
        "config": {
            "initial_balance": 100000, "leverage": 100,
            "commission_bps": 10, "slippage_points": 2,
            "spread_mult": 1.0, "swap_enabled": False, "margin_enabled": True,
        },
    })
    assert r.status_code == 401
