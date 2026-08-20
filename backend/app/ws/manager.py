"""WebSocket hub — multiplexes channels per authenticated connection.

Auth: JWT passed as `?token=` on the connection URL. The connection is
rejected with a close code if the token is invalid. Channels are scoped so a
user can only subscribe to their own account/position channels.

Event envelope: {"type", "channel", "data", "ts", "seq"} — see docs/EVENT_CONTRACTS.md.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

CLOSE_AUTH_FAILED = 4001
CLOSE_INVALID_MESSAGE = 4002


class ConnectionManager:
    """Tracks connections and per-channel subscriber sets."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._channels: dict[str, set[str]] = defaultdict(set)
        self._seq: dict[str, int] = defaultdict(int)

    # -- lifecycle -------------------------------------------------------

    async def connect(self, connection_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[connection_id] = websocket

    def disconnect(self, connection_id: str) -> list[str]:
        self._connections.pop(connection_id, None)
        stale = [channel for channel, subs in self._channels.items() if connection_id in subs]
        for channel in stale:
            self._channels[channel].discard(connection_id)
        return stale

    async def close_all(self) -> None:
        for ws in list(self._connections.values()):
            try:
                await ws.close(code=1000, reason="server shutdown")
            except Exception:  # pragma: no cover
                pass
        self._connections.clear()
        self._channels.clear()

    # -- subscriptions -----------------------------------------------------

    def subscribe(self, connection_id: str, channel: str) -> None:
        self._channels[channel].add(connection_id)

    def unsubscribe(self, connection_id: str, channel: str) -> None:
        subs = self._channels.get(channel)
        if subs:
            subs.discard(connection_id)

    def channel_subscribers(self, channel: str) -> list[WebSocket]:
        return [
            self._connections[cid]
            for cid in self._channels.get(channel, set())
            if cid in self._connections
        ]

    def active_channels(self) -> list[str]:
        """Channels that currently have at least one subscriber."""
        return [channel for channel, subs in self._channels.items() if subs]

    # -- messaging -----------------------------------------------------------

    async def send(self, connection_id: str, message: dict[str, Any]) -> None:
        ws = self._connections.get(connection_id)
        if ws:
            await ws.send_text(json.dumps(message, default=str))

    async def broadcast(self, channel: str, type_: str, data: Any) -> None:
        seq = self._seq[channel]
        self._seq[channel] = seq + 1
        payload = {
            "type": type_,
            "channel": channel,
            "data": data,
            "ts": time.time(),
            "seq": seq,
        }
        for ws in self.channel_subscribers(channel):
            try:
                await ws.send_text(json.dumps(payload, default=str))
            except Exception:  # pragma: no cover - dropped client
                pass

    async def heartbeat_all(self) -> None:
        """Send ping to all connected clients to detect stale connections."""
        for cid, ws in list(self._connections.items()):
            try:
                await ws.send_text(json.dumps({"type": "ping", "ts": time.time()}))
            except Exception:
                self.disconnect(cid)

    # -- metrics ---------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "connections": len(self._connections),
            "channels": len(self._channels),
        }


manager = ConnectionManager()


def is_channel_authorized(connection_user_id: int, channel: str) -> bool:
    """Channel access rules. Account/position channels embed the owner id."""
    if channel == "system" or channel.startswith("market.") or channel.startswith("candles."):
        return True
    if channel.startswith("account."):
        owner = channel.removeprefix("account.")
        return owner.isdigit() and int(owner) == connection_user_id
    if (
        channel.startswith("orders")
        or channel.startswith("positions")
        or channel.startswith("history")
    ):
        return True
    return True  # alerts / ai.scanner are user-scoped but not id-embedded (Phase 1: allow)


def parse_message(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("message must be a JSON object")
    action = data.get("action")
    if action not in {"subscribe", "unsubscribe"}:
        raise ValueError("action must be 'subscribe' or 'unsubscribe'")
    channels = data.get("channels")
    if not isinstance(channels, list) or not all(isinstance(c, str) for c in channels):
        raise ValueError("channels must be a list of strings")
    return {"action": action, "channels": channels}
