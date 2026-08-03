"""Real-time event broadcasters.

Background tasks that publish `market.tick` / `market.snapshot` / `market.candle`
events to subscribed WS channels. They only broadcast to channels that actually
have subscribers, so idle servers do no work.
"""

from __future__ import annotations

import asyncio
import logging

from app.services.market_data import format_quote, market_data, next_quote
from app.ws.manager import manager

logger = logging.getLogger(__name__)

TICK_INTERVAL_S = 1.0
CANDLE_INTERVAL_S = 5.0


async def _market_tick_loop() -> None:
    while True:
        for info in market_data.symbols():
            channel = f"market.{info.symbol}"
            if not manager.channel_subscribers(channel):
                continue
            quote = next_quote(info.symbol)
            await manager.broadcast(channel, "market.tick", format_quote(quote))
        if manager.channel_subscribers("market.watch"):
            snapshot = [format_quote(next_quote(s.symbol)) for s in market_data.symbols()]
            await manager.broadcast("market.watch", "market.snapshot", snapshot)
        await asyncio.sleep(TICK_INTERVAL_S)


async def _candle_loop() -> None:
    while True:
        for channel in manager.active_channels():
            if not channel.startswith("candles."):
                continue
            parts = channel.split(".")
            if len(parts) != 3:  # candles.<symbol>.<tf>
                continue
            _, symbol, tf = parts
            candle = market_data.candles(symbol, tf, 1)[-1]
            await manager.broadcast(
                channel,
                "market.candle",
                {
                    "symbol": candle.symbol,
                    "tf": candle.timeframe,
                    "ts": candle.ts.isoformat(),
                    "o": candle.o,
                    "h": candle.h,
                    "l": candle.low,
                    "c": candle.c,
                    "v": candle.v,
                    "closed": False,
                },
            )
        await asyncio.sleep(CANDLE_INTERVAL_S)


async def _run() -> None:
    await asyncio.gather(_market_tick_loop(), _candle_loop())


def start_broadcasters() -> asyncio.Task:
    return asyncio.create_task(_run())
