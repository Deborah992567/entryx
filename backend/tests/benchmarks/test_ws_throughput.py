"""WebSocket manager throughput and serialization benchmarks."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock

from app.ws.manager import ConnectionManager, parse_message


def _make_mock_ws() -> AsyncMock:
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


def test_broadcast_throughput_100_clients() -> None:
    mgr = ConnectionManager()
    for i in range(100):
        cid = f"c{i}"
        mgr._connections[cid] = _make_mock_ws()
        mgr.subscribe(cid, "market.EURUSD")

    data = {"symbol": "EURUSD", "bid": 1.1, "ask": 1.1002, "spread": 0.0002}
    t0 = time.perf_counter()
    for _ in range(1000):
        payload = {
            "type": "market.tick", "channel": "market.EURUSD",
            "data": data, "ts": time.time(), "seq": 0,
        }
        body = json.dumps(payload, default=str)
        for ws in mgr.channel_subscribers("market.EURUSD"):
            ws.send_text(body)
    elapsed = time.perf_counter() - t0
    events_per_sec = (1000 * 100) / elapsed
    print(f"  100 clients x 1000 broadcasts: {elapsed:.3f}s ({events_per_sec:.0f} events/s)")
    assert events_per_sec > 100


def test_broadcast_throughput_500_clients() -> None:
    mgr = ConnectionManager()
    for i in range(500):
        cid = f"c{i}"
        mgr._connections[cid] = _make_mock_ws()
        mgr.subscribe(cid, "market.EURUSD")

    data = {"symbol": "EURUSD", "bid": 1.1, "ask": 1.1002, "spread": 0.0002}
    t0 = time.perf_counter()
    for _ in range(500):
        payload = {
            "type": "market.tick", "channel": "market.EURUSD",
            "data": data, "ts": time.time(), "seq": 0,
        }
        body = json.dumps(payload, default=str)
        for ws in mgr.channel_subscribers("market.EURUSD"):
            ws.send_text(body)
    elapsed = time.perf_counter() - t0
    events_per_sec = (500 * 500) / elapsed
    print(f"  500 clients x 500 broadcasts: {elapsed:.3f}s ({events_per_sec:.0f} events/s)")
    assert events_per_sec > 100


def test_json_serialization_throughput() -> None:
    payload = {
        "type": "market.tick",
        "channel": "market.EURUSD",
        "data": {"symbol": "EURUSD", "bid": 1.12345, "ask": 1.12367, "spread": 0.00022, "volume": 1234.5},
        "ts": time.time(),
        "seq": 42,
    }
    t0 = time.perf_counter()
    for _ in range(10000):
        json.dumps(payload, default=str)
    elapsed = time.perf_counter() - t0
    rate = 10000 / elapsed
    print(f"  JSON serialization: 10000 in {elapsed:.3f}s ({rate:.0f} msg/s)")
    assert rate > 1000


def test_parse_message_valid() -> None:
    msg = json.dumps({"action": "subscribe", "channels": ["market.EURUSD"]})
    result = parse_message(msg)
    assert result["action"] == "subscribe"
    assert result["channels"] == ["market.EURUSD"]


def test_parse_message_invalid_action() -> None:
    import pytest
    with pytest.raises(ValueError, match="action"):
        parse_message(json.dumps({"action": "ping", "channels": ["x"]}))


def test_parse_message_invalid_channels() -> None:
    import pytest
    with pytest.raises(ValueError, match="channels"):
        parse_message(json.dumps({"action": "subscribe", "channels": "not_a_list"}))


def test_manager_stats() -> None:
    mgr = ConnectionManager()
    mgr._connections["c1"] = _make_mock_ws()
    mgr.subscribe("c1", "market.EURUSD")
    stats = mgr.stats()
    assert stats["connections"] == 1
    assert stats["channels"] == 1
    assert stats["active_subscriptions"] == 1
