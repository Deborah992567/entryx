"""WebSocket real-time broadcast tests (Phase 2)."""

from __future__ import annotations

import time

from app.core import security
from app.core.config import get_settings


def _token(user_id: int = 1) -> str:
    return security.create_access_token(str(user_id), get_settings())


def test_ws_receives_market_tick(client):
    with client.websocket_connect(f"/ws?token={_token()}") as ws:
        ws.send_json({"action": "subscribe", "channels": ["market.EURUSD"]})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "system.subscribed":
                continue
            if msg["type"] == "market.tick":
                assert msg["channel"] == "market.EURUSD"
                assert msg["data"]["bid"] < msg["data"]["ask"]
                assert msg["data"]["symbol"] == "EURUSD"
                break
            if time.monotonic() > 10:
                raise AssertionError("no market.tick received in time")


def test_ws_receives_candle_event(client):
    with client.websocket_connect(f"/ws?token={_token()}") as ws:
        ws.send_json({"action": "subscribe", "channels": ["candles.XAUUSD.M1"]})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "system.subscribed":
                continue
            if msg["type"] == "market.candle":
                assert msg["channel"] == "candles.XAUUSD.M1"
                assert msg["data"]["symbol"] == "XAUUSD"
                assert msg["data"]["l"] <= min(msg["data"]["o"], msg["data"]["c"])
                break
            if time.monotonic() > 10:
                raise AssertionError("no market.candle received in time")


def test_ws_receives_market_snapshot(client):
    with client.websocket_connect(f"/ws?token={_token()}") as ws:
        ws.send_json({"action": "subscribe", "channels": ["market.watch"]})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "system.subscribed":
                continue
            if msg["type"] == "market.snapshot":
                assert isinstance(msg["data"], list)
                assert len(msg["data"]) >= 10
                break
            if time.monotonic() > 10:
                raise AssertionError("no market.snapshot received in time")


def test_ws_receives_position_and_account_events(client, auth_headers):
    user_id = 1
    with client.websocket_connect(f"/ws?token={_token(user_id=user_id)}") as ws:
        ws.send_json(
            {
                "action": "subscribe",
                "channels": [f"account.{user_id}", "positions", "orders", "history"],
            }
        )
        # wait for the four subscription acks
        acks = 0
        while acks < 4:
            if ws.receive_json()["type"] == "system.subscribed":
                acks += 1

        order = client.post(
            "/api/v1/trading/orders",
            headers=auth_headers,
            json={"symbol": "EURUSD", "side": "buy", "type": "market", "volume": 0.3},
        )
        assert order.status_code == 201

        seen = {"order.created", "position.opened", "account.updated"}
        received: set[str] = set()
        for _ in range(3):
            msg = ws.receive_json()
            received.add(msg["type"])
        assert seen <= received

        position_id = client.get("/api/v1/trading/positions", headers=auth_headers).json()[0]["id"]
        closed = client.delete(f"/api/v1/trading/positions/{position_id}", headers=auth_headers)
        assert closed.status_code == 200

        seen_closed = {"position.closed", "trade.closed", "account.updated"}
        received_closed: set[str] = set()
        for _ in range(3):
            msg = ws.receive_json()
            received_closed.add(msg["type"])
        assert seen_closed <= received_closed
