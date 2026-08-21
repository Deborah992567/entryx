"""WebSocket endpoint wiring — authenticates, then multiplexes subscriptions.

On auth failure the socket is closed with code 4001 before accept; the
endpoint returns cleanly (no exception escapes into the ASGI layer).
"""

from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.ws.manager import (
    CLOSE_AUTH_FAILED,
    CLOSE_TOO_MANY_CONNECTIONS,
    MAX_CONNECTIONS_PER_USER,
    MAX_MESSAGE_BYTES,
    is_channel_authorized,
    manager,
    parse_message,
)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    settings = get_settings()
    token = websocket.query_params.get("token", "")
    try:
        payload = decode_access_token(token, settings)
        user_id = int(payload["sub"])
    except Exception:
        await websocket.close(code=CLOSE_AUTH_FAILED, reason="unauthorized")
        return

    connection_id = f"u{user_id}:{uuid.uuid4().hex[:8]}"

    if manager.user_connection_count(user_id) >= MAX_CONNECTIONS_PER_USER:
        await websocket.close(code=CLOSE_TOO_MANY_CONNECTIONS, reason="too many connections")
        return

    await manager.connect(connection_id, websocket)
    manager.track_user(connection_id, user_id)
    await manager.send(
        connection_id,
        {
            "type": "system.connected",
            "channel": "system",
            "data": {"connection_id": connection_id, "user_id": user_id},
            "ts": time.time(),
            "seq": 0,
        },
    )
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
                await manager.send(
                    connection_id,
                    {
                        "type": "system.error",
                        "channel": "system",
                        "data": {"code": "ERR_WS", "message": "message too large"},
                    },
                )
                continue
            try:
                msg = parse_message(raw)
            except (ValueError, json.JSONDecodeError) as exc:
                await manager.send(
                    connection_id,
                    {
                        "type": "system.error",
                        "channel": "system",
                        "data": {"code": "ERR_WS", "message": str(exc)},
                    },
                )
                continue

            action, channels = msg["action"], msg["channels"]
            for channel in channels:
                if not is_channel_authorized(user_id, channel):
                    await manager.send(
                        connection_id,
                        {
                            "type": "system.error",
                            "channel": "system",
                            "data": {
                                "code": "ERR_FORBIDDEN",
                                "message": f"channel '{channel}' not allowed",
                            },
                        },
                    )
                    continue
                if action == "subscribe":
                    manager.subscribe(connection_id, channel)
                else:
                    manager.unsubscribe(connection_id, channel)
                await manager.send(
                    connection_id,
                    {
                        "type": "system.subscribed"
                        if action == "subscribe"
                        else "system.unsubscribed",
                        "channel": channel,
                        "data": {"channel": channel},
                        "ts": time.time(),
                        "seq": 0,
                    },
                )
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(connection_id)
