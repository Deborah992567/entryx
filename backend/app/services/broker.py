"""Broker adapter abstraction and the in-memory paper broker.

The paper broker fills orders against the market data provider, tracks
positions and orders, and computes margin/P&L. It is fully deterministic
given the underlying provider, so tests and the real-time engine can rely on
repeatable behaviour.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.market_data import MarketDataProvider, Quote

COMMISSION_RATE = 0.00002  # 2 bps of notional per side


class BrokerError(Exception):
    """Base error for broker operations."""


class InsufficientMarginError(BrokerError):
    """Raised when an order would exceed available free margin."""


class InvalidOrderError(BrokerError):
    """Raised when an order request is malformed."""


class UnknownRefError(BrokerError):
    """Raised when an order or position id does not exist."""


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str  # buy | sell
    type: str  # market | limit | stop
    volume: float
    price: float | None = None  # required for limit / stop
    sl: float | None = None
    tp: float | None = None
    magic: int = 0
    comment: str = ""


@dataclass(frozen=True)
class BrokerOrder:
    id: str
    symbol: str
    side: str
    type: str
    volume: float
    price: float | None
    state: str  # pending | filled | cancelled | rejected
    filled_price: float | None
    sl: float | None
    tp: float | None
    magic: int
    comment: str
    created_at: datetime


@dataclass(frozen=True)
class BrokerPosition:
    id: str
    symbol: str
    side: str
    volume: float
    open_price: float
    sl: float | None
    tp: float | None
    opened_at: datetime
    commission: float


@dataclass(frozen=True)
class ClosedTrade:
    id: str
    symbol: str
    side: str
    volume: float
    open_price: float
    close_price: float
    gross_pnl: float
    net_pnl: float
    commission: float
    closed_at: datetime


@dataclass
class BrokerAccount:
    number: str
    currency: str = "USD"
    balance: float = 100_000.0
    leverage: float = 100.0


class BrokerAdapter(ABC):
    """Interface every broker implementation (paper or live) must satisfy."""

    @abstractmethod
    def account(self) -> BrokerAccount: ...

    @abstractmethod
    def deposit(self, amount: float) -> None: ...

    @abstractmethod
    def withdraw(self, amount: float) -> None: ...

    @abstractmethod
    def place_order(self, request: OrderRequest) -> BrokerOrder: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> BrokerOrder: ...

    @abstractmethod
    def close_position(self, position_id: str, price: float | None = None) -> ClosedTrade: ...

    @abstractmethod
    def order(self, order_id: str) -> BrokerOrder: ...

    @abstractmethod
    def position(self, position_id: str) -> BrokerPosition: ...

    @abstractmethod
    def pending_orders(self) -> list[BrokerOrder]: ...

    @abstractmethod
    def open_positions(self) -> list[BrokerPosition]: ...

    @abstractmethod
    def floating_pnl(self, position: BrokerPosition, quote: Quote) -> float: ...

    @abstractmethod
    def margin_required(self, symbol: str, volume: float, price: float) -> float: ...

    @abstractmethod
    def equity(self) -> float: ...


class PaperBroker(BrokerAdapter):
    """In-memory paper broker filled against a `MarketDataProvider`."""

    def __init__(self, provider: MarketDataProvider, *, initial_balance: float = 100_000.0) -> None:
        self._provider = provider
        self._account = BrokerAccount(number="0001-PAPER", balance=initial_balance)
        self._orders: dict[str, BrokerOrder] = {}
        self._positions: dict[str, BrokerPosition] = {}
        self._closed: list[ClosedTrade] = []

    # -- account --------------------------------------------------------------

    def account(self) -> BrokerAccount:
        return self._account

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise InvalidOrderError("deposit must be positive")
        self._account.balance += amount

    def withdraw(self, amount: float) -> None:
        if amount <= 0:
            raise InvalidOrderError("withdraw must be positive")
        if amount > self._account.balance:
            raise InsufficientMarginError("cannot withdraw more than balance")
        self._account.balance -= amount

    # -- orders ---------------------------------------------------------------

    def place_order(self, request: OrderRequest) -> BrokerOrder:
        _validate_request(request)
        symbol = request.symbol.upper()
        info = self._provider.symbol_info(symbol)
        volume = round(request.volume, 4)
        if volume <= 0:
            raise InvalidOrderError("volume must be positive")

        if request.type == "market":
            quote = self._provider.quote(symbol)
            fill_price = quote.ask if request.side == "buy" else quote.bid
            return self._fill(
                request, symbol=symbol, volume=volume, price=fill_price, state="filled"
            )

        if request.price is None:
            raise InvalidOrderError("limit/stop orders require a price")
        price = round(request.price, info.digits)
        quote = self._provider.quote(symbol)
        if _is_crossed(request.side, request.type, quote, price):
            return self._fill(request, symbol=symbol, volume=volume, price=price, state="filled")

        order = BrokerOrder(
            id=_new_id("o"),
            symbol=symbol,
            side=request.side,
            type=request.type,
            volume=volume,
            price=price,
            state="pending",
            filled_price=None,
            sl=request.sl,
            tp=request.tp,
            magic=request.magic,
            comment=request.comment,
            created_at=datetime.now(UTC),
        )
        self._orders[order.id] = order
        return order

    def cancel_order(self, order_id: str) -> BrokerOrder:
        order = self._orders.get(order_id)
        if order is None:
            raise UnknownRefError(f"unknown order: {order_id}")
        if order.state != "pending":
            raise BrokerError(f"cannot cancel order in state {order.state}")
        cancelled = _replace(order, state="cancelled")
        self._orders[order_id] = cancelled
        return cancelled

    # -- positions ------------------------------------------------------------

    def close_position(self, position_id: str, price: float | None = None) -> ClosedTrade:
        position = self._positions.get(position_id)
        if position is None:
            raise UnknownRefError(f"unknown position: {position_id}")
        quote = self._provider.quote(position.symbol)
        close_price = price if price is not None else (quote.bid if position.side == "buy" else quote.ask)
        info = self._provider.symbol_info(position.symbol)
        close_price = round(close_price, info.digits)
        gross = self.floating_pnl(position, quote)
        notional = close_price * info.contract_size * position.volume
        commission = round(notional * COMMISSION_RATE, 2)
        net = round(gross - commission - position.commission, 2)
        trade = ClosedTrade(
            id=_new_id("t"),
            symbol=position.symbol,
            side=position.side,
            volume=position.volume,
            open_price=position.open_price,
            close_price=close_price,
            gross_pnl=round(gross, 2),
            net_pnl=net,
            commission=commission,
            closed_at=datetime.now(UTC),
        )
        self._account.balance = round(self._account.balance + net, 2)
        del self._positions[position_id]
        self._closed.append(trade)
        return trade

    # -- queries --------------------------------------------------------------

    def order(self, order_id: str) -> BrokerOrder:
        try:
            return self._orders[order_id]
        except KeyError as exc:
            raise UnknownRefError(f"unknown order: {order_id}") from exc

    def position(self, position_id: str) -> BrokerPosition:
        try:
            return self._positions[position_id]
        except KeyError as exc:
            raise UnknownRefError(f"unknown position: {position_id}") from exc

    def pending_orders(self) -> list[BrokerOrder]:
        return [o for o in self._orders.values() if o.state == "pending"]

    def open_positions(self) -> list[BrokerPosition]:
        return list(self._positions.values())

    def closed_trades(self) -> list[ClosedTrade]:
        return list(self._closed)

    def floating_pnl(self, position: BrokerPosition, quote: Quote) -> float:
        info = self._provider.symbol_info(position.symbol)
        direction = 1.0 if position.side == "buy" else -1.0
        return (quote.bid - position.open_price) * direction * info.contract_size * position.volume

    def margin_required(self, symbol: str, volume: float, price: float) -> float:
        info = self._provider.symbol_info(symbol)
        return price * info.contract_size * volume / self._account.leverage

    def margin_used(self) -> float:
        total = 0.0
        for position in self._positions.values():
            quote = self._provider.quote(position.symbol)
            total += self.margin_required(position.symbol, position.volume, quote.bid)
        return round(total, 2)

    def floating_pnl_total(self) -> float:
        total = 0.0
        for position in self._positions.values():
            total += self.floating_pnl(position, self._provider.quote(position.symbol))
        return round(total, 2)

    def equity(self) -> float:
        return round(self._account.balance + self.floating_pnl_total(), 2)

    # -- internals ------------------------------------------------------------

    def _fill(self, request: OrderRequest, *, symbol: str, volume: float, price: float, state: str) -> BrokerOrder:
        info = self._provider.symbol_info(symbol)
        margin = self.margin_required(symbol, volume, price)
        if margin > self._account.balance:
            return BrokerOrder(
                id=_new_id("o"),
                symbol=symbol,
                side=request.side,
                type=request.type,
                volume=volume,
                price=price,
                state="rejected",
                filled_price=None,
                sl=request.sl,
                tp=request.tp,
                magic=request.magic,
                comment=request.comment,
                created_at=datetime.now(UTC),
            )
        notional = price * info.contract_size * volume
        commission = round(notional * COMMISSION_RATE, 2)
        order = BrokerOrder(
            id=_new_id("o"),
            symbol=symbol,
            side=request.side,
            type=request.type,
            volume=volume,
            price=price,
            state=state,
            filled_price=price,
            sl=request.sl,
            tp=request.tp,
            magic=request.magic,
            comment=request.comment,
            created_at=datetime.now(UTC),
        )
        self._orders[order.id] = order
        position = BrokerPosition(
            id=_new_id("p"),
            symbol=symbol,
            side=request.side,
            volume=volume,
            open_price=price,
            sl=request.sl,
            tp=request.tp,
            opened_at=order.created_at,
            commission=commission,
        )
        self._positions[position.id] = position
        self._account.balance = round(self._account.balance - commission, 2)
        return order


def _new_id(kind: str) -> str:
    return f"{kind}-{uuid.uuid4().hex[:12]}"


def _replace(order: BrokerOrder, **kwargs) -> BrokerOrder:
    return BrokerOrder(
        id=kwargs.get("id", order.id),
        symbol=kwargs.get("symbol", order.symbol),
        side=kwargs.get("side", order.side),
        type=kwargs.get("type", order.type),
        volume=kwargs.get("volume", order.volume),
        price=kwargs.get("price", order.price),
        state=kwargs.get("state", order.state),
        filled_price=kwargs.get("filled_price", order.filled_price),
        sl=kwargs.get("sl", order.sl),
        tp=kwargs.get("tp", order.tp),
        magic=kwargs.get("magic", order.magic),
        comment=kwargs.get("comment", order.comment),
        created_at=kwargs.get("created_at", order.created_at),
    )


def _validate_request(request: OrderRequest) -> None:
    if request.side not in {"buy", "sell"}:
        raise InvalidOrderError("side must be 'buy' or 'sell'")
    if request.type not in {"market", "limit", "stop"}:
        raise InvalidOrderError("type must be 'market', 'limit' or 'stop'")


def _is_crossed(side: str, order_type: str, quote: Quote, price: float) -> bool:
    if order_type == "limit":
        return quote.ask <= price if side == "buy" else quote.bid >= price
    if order_type == "stop":
        return quote.ask >= price if side == "buy" else quote.bid <= price
    return False
