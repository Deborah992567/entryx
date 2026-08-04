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
    type: str  # market | limit | stop | stop_limit
    volume: float
    price: float | None = None  # required for limit / stop / stop_limit
    limit_price: float | None = None  # required for stop_limit
    sl: float | None = None
    tp: float | None = None
    magic: int = 0
    comment: str = ""
    expiry: datetime | None = None  # pending orders only


@dataclass(frozen=True)
class BrokerOrder:
    id: str
    symbol: str
    side: str
    type: str
    volume: float
    price: float | None
    state: str  # pending | filled | cancelled | rejected | expired
    filled_price: float | None
    sl: float | None
    tp: float | None
    magic: int
    comment: str
    created_at: datetime
    limit_price: float | None = None
    expiry: datetime | None = None
    triggered: bool = False  # stop-limit: stop level crossed


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
        expiry = request.expiry
        if expiry is not None:
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            if expiry <= datetime.now(UTC):
                raise InvalidOrderError("expiry must be in the future")
        quote = self._provider.quote(symbol)

        if request.type == "market":
            fill_price = quote.ask if request.side == "buy" else quote.bid
            _validate_sl_tp(request.side, fill_price, request.sl, request.tp)
            return self._fill(
                request, symbol=symbol, volume=volume, price=round(fill_price, info.digits), state="filled"
            )

        if request.price is None:
            raise InvalidOrderError("limit/stop/stop-limit orders require a price")
        price = round(request.price, info.digits)
        if request.type == "stop_limit":
            if request.limit_price is None:
                raise InvalidOrderError("stop-limit orders require a limit_price")
            limit_price = round(request.limit_price, info.digits)
            _validate_stop_limit(request.side, price, limit_price)
        else:
            limit_price = None
        _validate_sl_tp(request.side, price, request.sl, request.tp)

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
            limit_price=limit_price,
            expiry=expiry,
        )
        self._orders[order.id] = order
        filled = self._maybe_fill(order, quote)
        return filled if filled is not None else order

    def cancel_order(self, order_id: str) -> BrokerOrder:
        order = self._orders.get(order_id)
        if order is None:
            raise UnknownRefError(f"unknown order: {order_id}")
        if order.state != "pending":
            raise BrokerError(f"cannot cancel order in state {order.state}")
        cancelled = _replace(order, state="cancelled")
        self._orders[order_id] = cancelled
        return cancelled

    def on_quote(self, symbol: str, *, now: datetime | None = None) -> list[tuple[str, BrokerOrder]]:
        """Process pending orders against the latest quote for ``symbol``.

        Expired pending orders transition to ``expired``; crossed limit/stop/
        stop-limit orders fill. Returns ``(event, order)`` pairs the caller can
        broadcast on the wire.
        """
        quote = self._provider.quote(symbol)
        now = now or datetime.now(UTC)
        events: list[tuple[str, BrokerOrder]] = []
        for oid in list(self._orders):
            order = self._orders[oid]
            if order.symbol != symbol or order.state != "pending":
                continue
            if order.expiry is not None and order.expiry < now:
                expired = _replace(order, state="expired")
                self._orders[oid] = expired
                events.append(("order.expired", expired))
                continue
            filled = self._maybe_fill(order, quote)
            if filled is not None:
                events.append(("order.filled", filled))
        return events

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

    def _maybe_fill(self, order: BrokerOrder, quote: Quote) -> BrokerOrder | None:
        """Fill ``order`` against ``quote`` if its trigger conditions are met."""
        if order.type == "stop_limit":
            triggered = order.triggered
            if not triggered:
                stop_crossed = quote.ask >= order.price if order.side == "buy" else quote.bid <= order.price
                if stop_crossed:
                    triggered = True
                    order = _replace(order, triggered=True)
                    self._orders[order.id] = order
            if not triggered:
                return None
            limit_crossed = quote.ask <= order.limit_price if order.side == "buy" else quote.bid >= order.limit_price
            if not limit_crossed:
                return None
            return self._fill(
                order, symbol=order.symbol, volume=order.volume, price=order.limit_price, state="filled", order_id=order.id
            )
        if _is_crossed(order.side, order.type, quote, order.price):
            return self._fill(
                order, symbol=order.symbol, volume=order.volume, price=order.price, state="filled", order_id=order.id
            )
        return None

    def _fill(self, request: OrderRequest, *, symbol: str, volume: float, price: float, state: str, order_id: str | None = None) -> BrokerOrder:
        info = self._provider.symbol_info(symbol)
        margin = self.margin_required(symbol, volume, price)
        oid = order_id or _new_id("o")
        if margin > self._account.balance:
            return BrokerOrder(
                id=oid,
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
                limit_price=request.limit_price,
                expiry=request.expiry,
            )
        notional = price * info.contract_size * volume
        commission = round(notional * COMMISSION_RATE, 2)
        order = BrokerOrder(
            id=oid,
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
            limit_price=request.limit_price,
            expiry=request.expiry,
        )
        self._orders[order.id] = order
        position = BrokerPosition(
            id=f"p-{oid[2:]}" if oid.startswith("o-") else f"p-{uuid.uuid4().hex[:12]}",
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
        limit_price=kwargs.get("limit_price", order.limit_price),
        expiry=kwargs.get("expiry", order.expiry),
        triggered=kwargs.get("triggered", order.triggered),
    )


def _validate_request(request: OrderRequest) -> None:
    if request.side not in {"buy", "sell"}:
        raise InvalidOrderError("side must be 'buy' or 'sell'")
    if request.type not in {"market", "limit", "stop", "stop_limit"}:
        raise InvalidOrderError("type must be 'market', 'limit', 'stop' or 'stop_limit'")


def _validate_sl_tp(side: str, price: float, sl: float | None, tp: float | None) -> None:
    if sl is not None:
        if side == "buy" and sl >= price:
            raise InvalidOrderError("buy stop loss must be below the entry price")
        if side == "sell" and sl <= price:
            raise InvalidOrderError("sell stop loss must be above the entry price")
    if tp is not None:
        if side == "buy" and tp <= price:
            raise InvalidOrderError("buy take profit must be above the entry price")
        if side == "sell" and tp >= price:
            raise InvalidOrderError("sell take profit must be below the entry price")
    if sl is not None and tp is not None:
        if side == "buy" and sl >= tp:
            raise InvalidOrderError("take profit must be above the stop loss")
        if side == "sell" and sl <= tp:
            raise InvalidOrderError("stop loss must be above the take profit")


def _validate_stop_limit(side: str, stop: float, limit: float) -> None:
    if side == "buy" and limit < stop:
        raise InvalidOrderError("buy stop-limit requires limit_price >= price")
    if side == "sell" and limit > stop:
        raise InvalidOrderError("sell stop-limit requires limit_price <= price")


def _is_crossed(side: str, order_type: str, quote: Quote, price: float) -> bool:
    if order_type == "limit":
        return quote.ask <= price if side == "buy" else quote.bid >= price
    if order_type == "stop":
        return quote.ask >= price if side == "buy" else quote.bid <= price
    return False
