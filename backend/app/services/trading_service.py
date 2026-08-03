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


def active_brokers() -> list[PaperBroker]:
    with _lock:
        return list(_brokers.values())


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
    }


def to_order_out(order: BrokerOrder) -> dict:
    return {
        "id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "type": order.type,
        "volume": order.volume,
        "price": order.price,
        "state": order.state,
        "filled_price": order.filled_price,
        "sl": order.sl,
        "tp": order.tp,
        "magic": order.magic,
        "comment": order.comment,
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


async def close_position(user_id: int, position_id: str) -> ClosedTrade:
    broker = get_broker(user_id)
    trade = broker.close_position(position_id)
    await manager.broadcast("positions", "position.closed", to_trade_out(trade))
    await manager.broadcast("history", "trade.closed", to_trade_out(trade))
    await manager.broadcast(f"account.{user_id}", "account.updated", account_summary(user_id))
    return trade
