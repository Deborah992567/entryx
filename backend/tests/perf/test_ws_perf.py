"""Performance benchmarks for WebSocket fan-out and message serialization."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock

from app.ws.manager import ConnectionManager


def _mock_ws() -> AsyncMock:
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


def test_ws_broadcast_fan_out_100() -> None:
    mgr = ConnectionManager()
    loop = asyncio.new_event_loop()
    for i in range(100):
        ws = _mock_ws()
        loop.run_until_complete(mgr.connect(f"c{i}", ws))
        mgr.subscribe(f"c{i}", "market.EURUSD")

    start = time.perf_counter()
    for _ in range(100):
        loop.run_until_complete(
            mgr.broadcast("market.EURUSD", "market.tick", {"bid": 1.1, "ask": 1.2})
        )
    elapsed = time.perf_counter() - start
    loop.close()
    assert elapsed < 5.0, f"WS fan-out too slow: {elapsed:.2f}s for 100 broadcasts to 100 clients"


def test_ws_broadcast_fan_out_500() -> None:
    mgr = ConnectionManager()
    loop = asyncio.new_event_loop()
    for i in range(500):
        ws = _mock_ws()
        loop.run_until_complete(mgr.connect(f"c{i}", ws))
        mgr.subscribe(f"c{i}", "market.EURUSD")

    start = time.perf_counter()
    loop.run_until_complete(
        mgr.broadcast("market.EURUSD", "market.tick", {"bid": 1.1, "ask": 1.2})
    )
    elapsed = time.perf_counter() - start
    loop.close()
    assert elapsed < 1.0, f"WS broadcast too slow: {elapsed:.2f}s for 1 broadcast to 500 clients"


def test_ws_message_serialization_performance() -> None:
    payload = {
        "type": "market.tick",
        "channel": "market.EURUSD",
        "data": {"bid": 1.12345, "ask": 1.12355, "spread": 0.0001, "symbol": "EURUSD"},
        "ts": time.time(),
        "seq": 42,
    }
    start = time.perf_counter()
    for _ in range(10000):
        json.dumps(payload, default=str)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"JSON serialization too slow: {elapsed:.2f}s for 10000 messages"
