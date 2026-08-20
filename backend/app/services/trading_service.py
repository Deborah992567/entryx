"""Per-user paper broker registry with WebSocket event emission.

Each authenticated user owns an in-memory `PaperBroker`. Every mutation
(place/cancel/close) publishes the corresponding `EVENT_CONTRACTS.md` events to
the WS hub after it is committed.
"""

from __future__ import annotations

import threading

from app.services.broker import (
    BrokerOrder,
    BrokerPosition,
    ClosedTrade,
    OrderRequest,
    PaperBroker,
)
from app.services.market_data import market_data
from app.services.strategy import strategy_engine
from app.ws.manager import manager

_lock = threading.Lock()
_brokers: dict[int, PaperBroker] = {}


def get_broker(user_id: int) -> PaperBroker:
    with _lock:
        broker = _brokers.get(user_id)
        if broker is None:
            broker = PaperBroker(market_data)
            _brokers[user_id] = broker
        return broker


def active_brokers() -> list[tuple[int, PaperBroker]]:
    with _lock:
        return list(_brokers.items())


def reset_brokers() -> None:
    """Drop all in-memory accounts (used by tests)."""
    with _lock:
        _brokers.clear()


def account_summary(user_id: int) -> dict:
    broker = get_broker(user_id)
    account = broker.account()
    equity = broker.equity()
    margin_used = broker.margin_used()
    free_margin = round(equity - margin_used, 2)
    margin_level = round(equity / margin_used * 100, 2) if margin_used > 0 else 0.0
    realized = round(sum(t.net_pnl for t in broker.closed_trades()), 2)
    return {
        "number": account.number,
        "currency": account.currency,
        "balance": account.balance,
        "equity": equity,
        "margin_used": margin_used,
        "free_margin": free_margin,
        "margin_level": margin_level,
        "floating_pnl": broker.floating_pnl_total(),
        "realized_pnl": realized,
        "commission": broker.commission_total(),
        "swap": broker.swap_total(),
        "exposure": broker.exposure(),
    }


def to_order_out(order: BrokerOrder) -> dict:
    return {
        "id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "type": order.type,
        "volume": order.volume,
        "price": order.price,
        "limit_price": order.limit_price,
        "state": order.state,
        "filled_price": order.filled_price,
        "sl": order.sl,
        "tp": order.tp,
        "magic": order.magic,
        "comment": order.comment,
        "expiry": order.expiry,
        "created_at": order.created_at,
    }


def to_position_out(position: BrokerPosition, floating_pnl: float = 0.0) -> dict:
    return {
        "id": position.id,
        "symbol": position.symbol,
        "side": position.side,
        "volume": position.volume,
        "open_price": position.open_price,
        "sl": position.sl,
        "tp": position.tp,
        "opened_at": position.opened_at,
        "commission": position.commission,
        "magic": position.magic,
        "trail": position.trail,
        "floating_pnl": floating_pnl,
    }


def to_trade_out(trade: ClosedTrade) -> dict:
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "volume": trade.volume,
        "open_price": trade.open_price,
        "close_price": trade.close_price,
        "gross_pnl": trade.gross_pnl,
        "net_pnl": trade.net_pnl,
        "commission": trade.commission,
        "swap": trade.swap,
        "closed_at": trade.closed_at,
    }


def list_positions(user_id: int) -> list[dict]:
    broker = get_broker(user_id)
    return [
        to_position_out(position, broker.floating_pnl(position, market_data.quote(position.symbol)))
        for position in broker.open_positions()
    ]


async def place_order(user_id: int, request: OrderRequest) -> BrokerOrder:
    broker = get_broker(user_id)
    order = broker.place_order(request)
    await manager.broadcast("orders", "order.created", to_order_out(order))
    if order.state == "filled":
        position = broker.position(order.id.replace("o-", "p-"))
        quote = market_data.quote(position.symbol)
        pnl = broker.floating_pnl(position, quote)
        await manager.broadcast("positions", "position.opened", to_position_out(position, pnl))
        await manager.broadcast(f"account.{user_id}", "account.updated", account_summary(user_id))
    return order


async def cancel_order(user_id: int, order_id: str) -> BrokerOrder:
    broker = get_broker(user_id)
    order = broker.cancel_order(order_id)
    await manager.broadcast("orders", "order.cancelled", to_order_out(order))
    return order


async def close_position(
    user_id: int, position_id: str, volume: float | None = None
) -> ClosedTrade:
    broker = get_broker(user_id)
    trade = broker.close_position(position_id, volume=volume)
    await manager.broadcast("positions", "position.closed", to_trade_out(trade))
    await manager.broadcast("history", "trade.closed", to_trade_out(trade))
    await manager.broadcast(f"account.{user_id}", "account.updated", account_summary(user_id))
    return trade


async def modify_position(user_id: int, position_id: str, **changes: object) -> BrokerPosition:
    broker = get_broker(user_id)
    position = broker.modify_position(position_id, **changes)
    quote = market_data.quote(position.symbol)
    pnl = broker.floating_pnl(position, quote)
    await manager.broadcast("positions", "position.updated", to_position_out(position, pnl))
    return position


async def process_market(symbol: str) -> None:
    """Evaluate pending orders and position protections against a fresh quote.

    Called by the market tick loop so pending orders fill/expire, SL/TP/trailing
    stops fire, and the resulting changes are broadcast in near real-time.
    """
    for user_id, broker in active_brokers():
        events = broker.on_quote(symbol)
        for kind, payload in events:
            if kind == "order.filled":
                await manager.broadcast("orders", "order.filled", to_order_out(payload))
                position = broker.position(payload.id.replace("o-", "p-"))
                quote = market_data.quote(position.symbol)
                pnl = broker.floating_pnl(position, quote)
                await manager.broadcast(
                    "positions", "position.opened", to_position_out(position, pnl)
                )
                await manager.broadcast(
                    f"account.{user_id}", "account.updated", account_summary(user_id)
                )
            elif kind == "order.expired":
                await manager.broadcast("orders", "order.expired", to_order_out(payload))
            elif kind == "position.closed":
                await manager.broadcast("positions", "position.closed", to_trade_out(payload))
                await manager.broadcast("history", "trade.closed", to_trade_out(payload))
                await manager.broadcast(
                    f"account.{user_id}", "account.updated", account_summary(user_id)
                )
    strategy_engine.feed_quote(symbol)
