"""Tests for market data API endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app


def _auth_headers() -> dict:
    from app.core import security
    from app.core.config import get_settings
    token = security.create_access_token("1", get_settings())
    return {"Authorization": f"Bearer {token}"}


def test_list_symbols() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/market/symbols", headers=_auth_headers())
    assert r.status_code == 200
    symbols = r.json()
    assert len(symbols) > 0
    assert all("symbol" in s for s in symbols)
    assert all("name" in s for s in symbols)
    assert all("digits" in s for s in symbols)


def test_list_symbols_unauthenticated() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/market/symbols")
    assert r.status_code == 401


def test_get_candles() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/market/candles?symbol=EURUSD&tf=M15&limit=10", headers=_auth_headers())
    assert r.status_code == 200
    candles = r.json()
    assert len(candles) == 10
    assert all("o" in c and "h" in c and "c" in c for c in candles)


def test_get_candles_invalid_symbol() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/market/candles?symbol=INVALID&tf=M15&limit=10", headers=_auth_headers())
    assert r.status_code == 404


def test_get_quote() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/market/quote?symbol=EURUSD", headers=_auth_headers())
    assert r.status_code == 200
    quote = r.json()
    assert "bid" in quote
    assert "ask" in quote
    assert quote["bid"] < quote["ask"]
    assert quote["symbol"] == "EURUSD"
