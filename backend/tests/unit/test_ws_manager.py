"""Tests for WebSocket connection manager edge cases."""

from __future__ import annotations

import json
import pytest

from app.ws.manager import (
    ConnectionManager,
    is_channel_authorized,
    parse_message,
)


def _ws_mock():
    from unittest.mock import AsyncMock
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.fixture
def mgr():
    return ConnectionManager()


@pytest.mark.asyncio
async def test_connect_and_disconnect(mgr: ConnectionManager) -> None:
    ws = _ws_mock()
    await mgr.connect("c1", ws)
    assert "c1" in mgr._connections
    mgr.disconnect("c1")
    assert "c1" not in mgr._connections


def test_subscribe_and_unsubscribe(mgr: ConnectionManager) -> None:
    mgr.subscribe("c1", "market.EURUSD")
    assert "c1" in mgr._channels["market.EURUSD"]
    mgr.unsubscribe("c1", "market.EURUSD")
    assert "c1" not in mgr._channels.get("market.EURUSD", set())


def test_disconnect_cleans_subscriptions(mgr: ConnectionManager) -> None:
    mgr.subscribe("c1", "market.EURUSD")
    mgr.subscribe("c1", "positions")
    stale = mgr.disconnect("c1")
    assert "market.EURUSD" in stale
    assert "positions" in stale


@pytest.mark.asyncio
async def test_channel_subscribers_only_returns_active(mgr: ConnectionManager) -> None:
    ws1 = _ws_mock()
    ws2 = _ws_mock()
    await mgr.connect("c1", ws1)
    await mgr.connect("c2", ws2)
    mgr.subscribe("c1", "test")
    mgr.subscribe("c2", "test")
    mgr.disconnect("c2")
    subs = mgr.channel_subscribers("test")
    assert len(subs) == 1


def test_active_channels(mgr: ConnectionManager) -> None:
    mgr.subscribe("c1", "a")
    mgr.subscribe("c1", "b")
    mgr.subscribe("c2", "a")
    assert set(mgr.active_channels()) == {"a", "b"}
    mgr.unsubscribe("c1", "b")
    mgr.unsubscribe("c2", "a")
    assert mgr.active_channels() == ["a"]


def test_stats(mgr: ConnectionManager) -> None:
    stats = mgr.stats()
    assert stats["connections"] == 0
    assert stats["channels"] == 0
    assert stats["users"] == 0
    assert stats["active_subscriptions"] == 0


@pytest.mark.asyncio
async def test_track_and_count_user_connections(mgr: ConnectionManager) -> None:
    await mgr.connect("c1", _ws_mock())
    await mgr.connect("c2", _ws_mock())
    mgr.track_user("c1", 1)
    mgr.track_user("c2", 1)
    assert mgr.user_connection_count(1) == 2
    await mgr.connect("c3", _ws_mock())
    mgr.track_user("c3", 2)
    assert mgr.user_connection_count(2) == 1


def test_is_channel_authorized_market() -> None:
    assert is_channel_authorized(1, "market.EURUSD")
    assert is_channel_authorized(1, "system")
    assert is_channel_authorized(1, "candles.XAUUSD.H1")


def test_is_channel_authorized_account() -> None:
    assert is_channel_authorized(42, "account.42")
    assert not is_channel_authorized(42, "account.99")


def test_is_channel_authorized_trading() -> None:
    assert is_channel_authorized(1, "orders")
    assert is_channel_authorized(1, "positions")
    assert is_channel_authorized(1, "history")


def test_parse_message_valid() -> None:
    msg = parse_message(json.dumps({"action": "subscribe", "channels": ["a", "b"]}))
    assert msg["action"] == "subscribe"
    assert msg["channels"] == ["a", "b"]


def test_parse_message_rejects_bad_action() -> None:
    with pytest.raises(ValueError):
        parse_message(json.dumps({"action": "delete", "channels": ["a"]}))


def test_parse_message_rejects_bad_channels() -> None:
    with pytest.raises(ValueError):
        parse_message(json.dumps({"action": "subscribe", "channels": "not-a-list"}))


def test_parse_message_rejects_non_dict() -> None:
    with pytest.raises(ValueError):
        parse_message("[]")


@pytest.mark.asyncio
async def test_heartbeat_all(mgr: ConnectionManager) -> None:
    ws = _ws_mock()
    await mgr.connect("c1", ws)
    await mgr.heartbeat_all()
    ws.send_text.assert_called_once()
    sent = json.loads(ws.send_text.call_args[0][0])
    assert sent["type"] == "ping"


@pytest.mark.asyncio
async def test_send_only_to_active_connections(mgr: ConnectionManager) -> None:
    ws = _ws_mock()
    await mgr.connect("c1", ws)
    mgr.disconnect("c1")
    await mgr.send("c1", {"type": "test"})
    ws.send_text.assert_not_called()
