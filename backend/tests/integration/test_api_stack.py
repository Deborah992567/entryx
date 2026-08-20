"""Integration tests for the full API stack (Phase 10).

Tests the FastAPI app with a test client, covering auth, market data,
trading, structure, SMC, AI, and safeguards endpoints.
"""

from __future__ import annotations

import pytest
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """Register a test user and return auth headers."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "test_phase10@example.com",
            "password": "TestPass123!",
            "name": "Test Phase10",
        },
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test_phase10@example.com",
            "password": "TestPass123!",
        },
    )
    data = resp.json()
    token = data.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


class TestMarketEndpoints:
    def test_candles(self, client, auth_headers):
        resp = client.get(
            "/api/v1/market/candles?symbol=XAUUSD&tf=H1&limit=50", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_symbols(self, client, auth_headers):
        resp = client.get("/api/v1/market/symbols", headers=auth_headers)
        assert resp.status_code == 200


class TestStructureEndpoint:
    def test_analyze(self, client, auth_headers):
        resp = client.get("/api/v1/structure?symbol=XAUUSD&tf=H1&limit=100", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "candles" in data


class TestSmcEndpoint:
    def test_smc_analysis(self, client, auth_headers):
        resp = client.get("/api/v1/smc?symbol=XAUUSD&tf=H1&limit=100", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "fvg" in data
        assert "order_blocks" in data
        assert "liquidity_pools" in data


class TestAiEndpoints:
    def test_health(self, client, auth_headers):
        resp = client.get("/api/v1/ai/health", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_models(self, client, auth_headers):
        resp = client.get("/api/v1/ai/models", headers=auth_headers)
        assert resp.status_code == 200

    def test_conversations(self, client, auth_headers):
        resp = client.get("/api/v1/ai/conversations", headers=auth_headers)
        assert resp.status_code == 200


class TestSafeguardsEndpoint:
    def test_get_safeguards(self, client, auth_headers):
        resp = client.get("/api/v1/safeguards", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "kill_switch" in data
        assert "live_enabled" in data

    def test_safeguards_status(self, client, auth_headers):
        resp = client.get("/api/v1/safeguards/status", headers=auth_headers)
        assert resp.status_code == 200

    def test_kill_switch_toggle(self, client, auth_headers):
        resp = client.post(
            "/api/v1/safeguards/kill-switch", json={"active": True}, headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["kill_switch"] is True
        # reset
        client.post("/api/v1/safeguards/kill-switch", json={"active": False}, headers=auth_headers)

    def test_update_safeguards(self, client, auth_headers):
        resp = client.put(
            "/api/v1/safeguards", json={"max_position_size": 5.0}, headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["max_position_size"] == 5.0
        # reset
        client.put("/api/v1/safeguards", json={"max_position_size": 10.0}, headers=auth_headers)


class TestTradingEndpoint:
    def test_account(self, client, auth_headers):
        resp = client.get("/api/v1/trading/account", headers=auth_headers)
        assert resp.status_code == 200

    def test_positions(self, client, auth_headers):
        resp = client.get("/api/v1/trading/positions", headers=auth_headers)
        assert resp.status_code == 200

    def test_orders(self, client, auth_headers):
        resp = client.get("/api/v1/trading/orders", headers=auth_headers)
        assert resp.status_code == 200
