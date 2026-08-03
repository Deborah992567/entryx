"""Market data API tests (Phase 2)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_market_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/market/symbols")
    assert resp.status_code == 401


def test_list_symbols(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/market/symbols", headers=auth_headers)
    assert resp.status_code == 200
    symbols = resp.json()
    assert len(symbols) >= 10
    eurusd = next(s for s in symbols if s["symbol"] == "EURUSD")
    assert eurusd["category"] == "forex"
    assert eurusd["digits"] == 5


def test_candles(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/market/candles?symbol=XAUUSD&tf=H1&limit=50", headers=auth_headers)
    assert resp.status_code == 200
    candles = resp.json()
    assert len(candles) == 50
    first = candles[0]
    assert set(first) >= {"symbol", "timeframe", "ts", "o", "h", "l", "c", "v"}
    assert first["l"] <= min(first["o"], first["c"])


def test_candles_validate_timeframe(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/market/candles?symbol=EURUSD&tf=XX", headers=auth_headers)
    assert resp.status_code == 422


def test_candles_unknown_symbol(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/market/candles?symbol=NOPE", headers=auth_headers)
    assert resp.status_code == 404


def test_quote(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/market/quote?symbol=USDJPY", headers=auth_headers)
    assert resp.status_code == 200
    quote = resp.json()
    assert quote["bid"] < quote["ask"]
    assert quote["spread"] == round(quote["ask"] - quote["bid"], 3)
