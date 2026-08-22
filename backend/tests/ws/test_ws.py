"""WebSocket hub tests: auth, subscribe/unsubscribe, error handling."""

from __future__ import annotations

import pytest
from app.core import security
from app.core.config import get_settings
from starlette.websockets import WebSocketDisconnect


def _token(user_id: int = 1) -> str:
    return security.create_access_token(str(user_id), get_settings())


def _connect(ws):
    """Consume the system.connected welcome message."""
    return ws.receive_json()


def test_ws_connect_without_token_rejected(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws"):
            pass
    assert exc.value.code == 4001


def test_ws_connect_with_bad_token_rejected(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws?token=not-a-jwt"):
            pass
    assert exc.value.code == 4001


def test_ws_connect_and_subscribe(client):
    with client.websocket_connect(f"/ws?token={_token()}") as ws:
        connected = _connect(ws)
        assert connected["type"] == "system.connected"
        ws.send_json({"action": "subscribe", "channels": ["system", "market.XAUUSD"]})
        first = ws.receive_json()
        assert first["type"] == "system.subscribed"
        assert first["channel"] == "system"
        second = ws.receive_json()
        assert second["type"] == "system.subscribed"
        assert second["channel"] == "market.XAUUSD"


def test_ws_unsubscribe(client):
    with client.websocket_connect(f"/ws?token={_token()}") as ws:
        _connect(ws)
        ws.send_json({"action": "subscribe", "channels": ["system"]})
        assert ws.receive_json()["type"] == "system.subscribed"
        ws.send_json({"action": "unsubscribe", "channels": ["system"]})
        assert ws.receive_json()["type"] == "system.unsubscribed"


def test_ws_rejects_bad_message(client):
    with client.websocket_connect(f"/ws?token={_token()}") as ws:
        _connect(ws)
        ws.send_json({"action": "nonsense", "channels": ["system"]})
        msg = ws.receive_json()
        assert msg["type"] == "system.error"
        assert msg["data"]["code"] == "ERR_WS"


def test_ws_rejects_foreign_account_channel(client):
    with client.websocket_connect(f"/ws?token={_token(user_id=1)}") as ws:
        _connect(ws)
        ws.send_json({"action": "subscribe", "channels": ["account.999"]})
        msg = ws.receive_json()
        assert msg["type"] == "system.error"
        assert msg["data"]["code"] == "ERR_FORBIDDEN"


def test_ws_allows_own_account_channel(client):
    with client.websocket_connect(f"/ws?token={_token(user_id=7)}") as ws:
        _connect(ws)
        ws.send_json({"action": "subscribe", "channels": ["account.7"]})
        assert ws.receive_json()["type"] == "system.subscribed"
