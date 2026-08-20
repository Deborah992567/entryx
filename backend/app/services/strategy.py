"""UI-independent strategy framework.

Strategies are plain Python classes driven by lifecycle hooks —
`initialize/on_tick/on_candle/on_signal/on_order/on_position/shutdown` — and
trade through a `StrategyContext` bound to a `BrokerAdapter`. The same
framework feeds live ticks (via the market loop) and, in Phase 5 L2, replays
historical candles in the backtester. Every hook is optional and every hook is
guarded so a crashing strategy never takes down the engine.
"""

from __future__ import annotations

import itertools
import threading
from abc import ABC
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.services.broker import BrokerAdapter, BrokerOrder, BrokerPosition, OrderRequest
from app.services.indicators import sma
from app.services.market_data import Candle, MarketDataProvider, Quote

MagicCounter = itertools.count(10_000)

SignalSide = str  # "buy" | "sell" | "close"


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: SignalSide
    reason: str
    price: float | None = None
    strength: float = 1.0
    ts: datetime | None = None
    meta: dict = field(default_factory=dict)


class StrategyError(Exception):
    """Raised for strategy configuration problems (not runtime hook errors)."""


class Strategy(ABC):
    """Base class every strategy implements.

    Hooks receive the strategy's `context` (set by the runner before
    `initialize`) plus the triggering object. Override only what you need —
    every hook defaults to a no-op.
    """

    name: str = ""
    description: str = ""
    default_params: dict = {}

    def __init__(self, params: dict | None = None) -> None:
        self.params = {**self.default_params, **(params or {})}
        self.context: StrategyContext | None = None

    def initialize(self) -> None:
        """Called once when the runner starts."""

    def on_tick(self, quote: Quote) -> None:
        """Called for every live market tick."""

    def on_candle(self, candle: Candle) -> None:
        """Called for every completed candle (live warm-up and backtest)."""

    def on_signal(self, signal: Signal) -> None:
        """Called for a signal the strategy emitted itself."""

    def on_order(self, order: BrokerOrder) -> None:
        """Called when an order owned by this strategy changes state."""

    def on_position(self, position: BrokerPosition) -> None:
        """Called when a position owned by this strategy opens or changes."""

    def shutdown(self) -> None:
        """Called once when the runner stops."""


class StrategyContext:
    """Trading surface handed to a strategy.

    The context owns the broker and routes every mutation back through the
    runner so `on_order` / `on_position` fire for the strategy's own orders.
    """

    def __init__(
        self,
        runner: StrategyRunner,
        *,
        provider: MarketDataProvider,
        symbol: str,
        magic: int,
        broker: BrokerAdapter,
    ) -> None:
        self._runner = runner
        self._provider = provider
        self.symbol = symbol
        self.magic = magic
        self.broker = broker

    # -- market access -------------------------------------------------------

    @property
    def now(self) -> datetime:
        return datetime.now(UTC)

    @property
    def symbol_info(self):
        return self._provider.symbol_info(self.symbol)

    @property
    def quote(self) -> Quote:
        return self._provider.quote(self.symbol)

    @property
    def orders(self) -> list[BrokerOrder]:
        return self.broker.pending_orders()

    @property
    def positions(self) -> list[BrokerPosition]:
        return self.broker.open_positions()

    # -- trading --------------------------------------------------------------

    def emit_signal(
        self,
        side: SignalSide,
        reason: str,
        *,
        price: float | None = None,
        strength: float = 1.0,
        **meta: object,
    ) -> Signal:
        signal = Signal(
            symbol=self.symbol,
            side=side,
            reason=reason,
            price=price,
            strength=strength,
            ts=self.now,
            meta=meta,
        )
        self._runner._handle_signal(signal)
        return signal

    def place_order(self, request: OrderRequest) -> BrokerOrder:
        request = OrderRequest(
            symbol=request.symbol,
            side=request.side,
            type=request.type,
            volume=request.volume,
            price=request.price,
            limit_price=request.limit_price,
            sl=request.sl,
            tp=request.tp,
            magic=self.magic,
            comment=request.comment or self._runner.instance_id,
            expiry=request.expiry,
        )
        order = self.broker.place_order(request)
        self._runner._note_order(order)
        return order

    def cancel_order(self, order_id: str) -> BrokerOrder:
        order = self.broker.cancel_order(order_id)
        self._runner._note_order(order)
        return order

    def close_position(self, position_id: str, *, price: float | None = None) -> object:
        return self.broker.close_position(position_id, price=price)


class StrategyRunner:
    """Runs one strategy instance and guards every hook call.

    Status lifecycle: ``idle`` -> ``running`` -> ``stopped`` (or ``error``).
    A hook exception transitions the runner to ``error`` and stops feeding —
    the strategy can then be inspected and restarted without affecting others.
    """

    def __init__(
        self,
        instance_id: str,
        strategy: Strategy,
        *,
        provider: MarketDataProvider,
        symbol: str,
        magic: int,
        broker: BrokerAdapter,
        timeframe: str = "H1",
    ) -> None:
        self.instance_id = instance_id
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.magic = magic
        self.status = "idle"
        self.last_error: str = ""
        self.signals: list[Signal] = []
        self.orders_placed = 0
        self.context = StrategyContext(
            self, provider=provider, symbol=symbol, magic=magic, broker=broker
        )

    # -- lifecycle ------------------------------------------------------------

    def start(self) -> None:
        if self.status not in {"idle", "stopped", "error"}:
            raise StrategyError(f"cannot start a strategy in state {self.status}")
        self.strategy.context = self.context
        self.status = "running"
        self._guard("initialize", self.strategy.initialize)

    def stop(self) -> dict:
        if self.status == "running":
            self.status = "stopped"
            self._guard("shutdown", self.strategy.shutdown)
        return self.summary()

    # -- event feed -----------------------------------------------------------

    def feed_quote(self, quote: Quote) -> None:
        if self.status == "running":
            self._guard("on_tick", self.strategy.on_tick, quote)

    def feed_candle(self, candle: Candle) -> None:
        if self.status == "running":
            self._guard("on_candle", self.strategy.on_candle, candle)

    def feed_order(self, order: BrokerOrder) -> None:
        if self.status == "running" and order.magic == self.magic:
            self._guard("on_order", self.strategy.on_order, order)

    def feed_position(self, position: BrokerPosition) -> None:
        if self.status == "running" and position.magic == self.magic:
            self._guard("on_position", self.strategy.on_position, position)

    def _handle_signal(self, signal: Signal) -> None:
        self.signals.append(signal)
        if self.status == "running":
            self._guard("on_signal", self.strategy.on_signal, signal)

    def _note_order(self, order: BrokerOrder) -> None:
        if order.magic != self.magic:
            return
        self.orders_placed += 1
        self.feed_order(order)
        if order.state == "filled":
            try:
                position = self.context.broker.position(order.id.replace("o-", "p-"))
            except Exception:  # pragma: no cover - position should exist for a fill
                position = None
            if position is not None:
                self.feed_position(position)

    # -- internals -------------------------------------------------------------

    def _guard(self, hook: str, fn, *args) -> None:
        try:
            fn(*args)
        except Exception as exc:  # hook errors must never escape
            self.status = "error"
            self.last_error = f"{hook}: {exc.__class__.__name__}: {exc}"

    def summary(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "strategy": self.strategy.name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "magic": self.magic,
            "status": self.status,
            "last_error": self.last_error,
            "signals_emitted": [signal_to_dict(s) for s in self.signals],
            "orders_placed": self.orders_placed,
        }


def signal_to_dict(signal: Signal) -> dict:
    return {
        "symbol": signal.symbol,
        "side": signal.side,
        "reason": signal.reason,
        "price": signal.price,
        "strength": signal.strength,
        "ts": (signal.ts or datetime.now(UTC)).isoformat(),
        "meta": signal.meta,
    }


# ---------------------------------------------------------------------------
# Built-in example strategies
# ---------------------------------------------------------------------------


class SmaCrossStrategy(Strategy):
    """Fast/slow SMA crossover.

    Emits a buy signal when the fast SMA crosses above the slow SMA and a
    sell signal when it crosses back down. On a buy signal it opens one market
    position (if none is open); on a sell signal it closes the open position.
    """

    name = "sma_cross"
    description = "SMA crossover: buy on fast/slow cross up, exit on cross down"
    default_params = {"fast": 10, "slow": 30, "volume": 0.1}

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        fast = int(self.params["fast"])
        slow = int(self.params["slow"])
        if fast <= 0 or slow <= 0:
            raise StrategyError("fast/slow periods must be positive")
        if fast >= slow:
            raise StrategyError("fast period must be smaller than slow period")
        self.fast = fast
        self.slow = slow
        self.volume = float(self.params.get("volume", 0.1))
        self._closes: list[float] = []

    def on_candle(self, candle: Candle) -> None:
        self._closes.append(candle.c)
        if len(self._closes) < self.slow + 1:
            return
        fast_series = sma(self._closes, self.fast)
        slow_series = sma(self._closes, self.slow)
        fast_now, fast_prev = fast_series[-1], fast_series[-2]
        slow_now, slow_prev = slow_series[-1], slow_series[-2]
        if None in (fast_now, fast_prev, slow_now, slow_prev):
            return
        if fast_prev <= slow_prev and fast_now > slow_now:
            self.context.emit_signal("buy", "fast SMA crossed above slow SMA", price=candle.c)
        elif fast_prev >= slow_prev and fast_now < slow_now:
            self.context.emit_signal("sell", "fast SMA crossed below slow SMA", price=candle.c)

    def on_signal(self, signal: Signal) -> None:
        context = self.context
        open_on_symbol = [p for p in context.positions if p.symbol == context.symbol]
        if signal.side == "buy":
            if open_on_symbol:
                return
            context.place_order(
                OrderRequest(
                    symbol=context.symbol,
                    side="buy",
                    type="market",
                    volume=self.volume,
                )
            )
        elif signal.side == "sell":
            for position in open_on_symbol:
                context.close_position(position.id)


# ---------------------------------------------------------------------------
# Registry + engine
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[Strategy]] = {}


def register_strategy(strategy_class: type[Strategy]) -> type[Strategy]:
    """Decorator registering a strategy class under its ``name``."""
    if not strategy_class.name:
        raise StrategyError("strategy must define a name")
    _REGISTRY[strategy_class.name] = strategy_class
    return strategy_class


@dataclass
class StrategyInstance:
    instance_id: str
    user_id: int
    strategy_name: str
    symbol: str
    timeframe: str
    runner: StrategyRunner


class StrategyEngine:
    """Owns running strategy instances and fans market data out to them."""

    def __init__(self) -> None:
        self._instances: dict[str, StrategyInstance] = {}
        self._lock = threading.Lock()

    def catalog(self) -> list[dict]:
        return [
            {
                "name": cls.name,
                "description": cls.description,
                "params": cls.default_params,
            }
            for cls in _REGISTRY.values()
        ]

    def start(
        self,
        *,
        user_id: int,
        name: str,
        symbol: str,
        provider: MarketDataProvider,
        broker: BrokerAdapter,
        params: dict | None = None,
        timeframe: str = "H1",
        candles: int = 300,
    ) -> dict:
        strategy_class = _REGISTRY.get(name)
        if strategy_class is None:
            raise KeyError(f"unknown strategy: {name}")
        instance_id = _new_instance_id()
        magic = next(MagicCounter)
        runner = StrategyRunner(
            instance_id,
            strategy_class(params),
            provider=provider,
            symbol=symbol.upper(),
            magic=magic,
            broker=broker,
            timeframe=timeframe,
        )
        with self._lock:
            self._instances[instance_id] = StrategyInstance(
                instance_id=instance_id,
                user_id=user_id,
                strategy_name=strategy_class.name,
                symbol=symbol.upper(),
                timeframe=timeframe,
                runner=runner,
            )
        runner.start()
        for candle in provider.candles(symbol, timeframe, candles):
            runner.feed_candle(candle)
        runner.feed_quote(provider.quote(symbol))
        return runner.summary()

    def stop(self, user_id: int, instance_id: str) -> dict:
        instance = self._instances.get(instance_id)
        if instance is None or instance.user_id != user_id:
            raise KeyError(f"unknown strategy instance: {instance_id}")
        summary = instance.runner.stop()
        with self._lock:
            self._instances.pop(instance_id, None)
        return summary

    def instances(self, user_id: int) -> list[dict]:
        return [
            instance.runner.summary()
            for instance in self._instances.values()
            if instance.user_id == user_id
        ]

    def feed_quote(self, symbol: str) -> None:
        """Dispatch a fresh quote to every running instance on ``symbol``."""
        for instance in list(self._instances.values()):
            if instance.symbol == symbol and instance.runner.status == "running":
                instance.runner.feed_quote(instance.runner.context.quote)

    def clear(self) -> None:
        with self._lock:
            self._instances.clear()


def _new_instance_id() -> str:
    import uuid

    return f"st-{uuid.uuid4().hex[:12]}"


register_strategy(SmaCrossStrategy)

strategy_engine = StrategyEngine()
