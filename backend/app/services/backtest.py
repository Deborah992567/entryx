"""UI-independent backtester (Phase 5 line 2, bar indices added in line 4).

Replays a historical candle series bar-by-bar through the same strategy
lifecycle used live (`StrategyRunner`), filling orders against a
`BacktestBroker` that mirrors `PaperBroker` semantics: commission, spread,
slippage, swap (per UTC rollover), leverage/margin, and SL/TP/trailing with
intra-bar resolution using each bar's open/high/low/close.

Fills are look-ahead-safe: a market order placed while processing bar *i*
fills at bar *i+1*'s open, and pending orders / protections resolve intra-bar
from the bar after they were placed. A given configuration always produces the
same result for the same candle series.
"""

from __future__ import annotations

import dataclasses
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.broker import (
    _UNSET,
    SWAP_POINTS_PER_LOT_DAY,
    BrokerAccount,
    BrokerOrder,
    BrokerPosition,
    ClosedTrade,
    InvalidOrderError,
    OrderRequest,
    UnknownRefError,
    _new_id,
    _replace,
    _replace_position,
    _validate_request,
    _validate_sl_tp,
    _validate_stop_limit,
)
from app.services.market_data import Candle, MarketDataProvider, Quote, market_data
from app.services.metrics import compute_metrics
from app.services.strategy import _REGISTRY, MagicCounter, StrategyRunner


@dataclass(frozen=True)
class BacktestConfig:
    """Execution parameters that shape a backtest run."""

    symbol: str
    timeframe: str = "H1"
    candle_count: int = 1000
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    initial_balance: float = 100_000.0
    leverage: int = 100
    commission_bps: float = 2.0  # per side
    slippage_points: float = 0.0  # adverse fill offset in price units
    spread_mult: float = 1.0  # multiplier on the symbol's natural spread
    swap_enabled: bool = True
    margin_enabled: bool = True


def config_to_dict(config: BacktestConfig) -> dict:
    out: dict = {}
    for field in dataclasses.fields(BacktestConfig):
        value = getattr(config, field.name)
        out[field.name] = value.isoformat() if isinstance(value, datetime) and value is not None else value
    return out


class BacktestBroker:
    """Replay broker that steps through a fixed candle series.

    Doubles as the market-data provider for the strategy runner (``quote`` /
    ``symbol_info`` / ``candles``) so `context.quote` reflects the bar being
    processed. Market orders fill at the next bar's open; pending orders and
    SL/TP/trailing resolve against bar OHLC with gap-aware prices.
    """

    def __init__(
        self,
        config: BacktestConfig,
        candles: list[Candle],
        *,
        on_order_update=None,
    ) -> None:
        self._config = config
        self._series = candles
        self._info = market_data.symbol_info(config.symbol)
        self._commission_rate = config.commission_bps / 10_000.0
        self._account = BrokerAccount(number="0001-PAPER", balance=config.initial_balance)
        self._orders: dict[str, BrokerOrder] = {}
        self._positions: dict[str, BrokerPosition] = {}
        self._closed: list[ClosedTrade] = []
        self._commission_total = 0.0
        self._candle: Candle | None = candles[0] if candles else None
        self._open_fill_ids: list[str] = []
        self._position_magic: dict[str, int] = {}
        self._trade_open: dict[str, datetime] = {}
        self.on_order_update = on_order_update

    # -- provider surface (used by StrategyContext) --------------------------

    def symbol_info(self, symbol: str):
        return market_data.symbol_info(symbol)

    def candles(self, symbol: str, timeframe: str, count: int, end_ts: datetime | None = None) -> list[Candle]:
        return self._series

    def quote(self, symbol: str, at: datetime | None = None) -> Quote:
        candle = self._candle
        if at is not None and candle is not None:
            for cand in self._series:
                if cand.ts >= at:
                    candle = cand
                    break
        if candle is None:
            raise ValueError("no bars to quote yet")
        bid, ask = self._bid_ask(candle.c)
        return Quote(
            symbol=symbol,
            ts=candle.ts,
            bid=bid,
            ask=ask,
            spread=round(self.spread, self._info.digits),
            change_pct=0.0,
            volume=candle.v,
        )

    @property
    def spread(self) -> float:
        return self._info.tick_size * 2 * self._config.spread_mult

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
            raise InvalidOrderError("cannot withdraw more than balance")
        self._account.balance -= amount

    # -- orders ---------------------------------------------------------------

    def place_order(self, request: OrderRequest) -> BrokerOrder:
        _validate_request(request)
        symbol = request.symbol.upper()
        volume = round(request.volume, 4)
        if volume <= 0:
            raise InvalidOrderError("volume must be positive")
        limit_price = None
        if request.type in {"limit", "stop", "stop_limit"}:
            if request.price is None:
                raise InvalidOrderError("limit/stop/stop-limit orders require a price")
            price = round(request.price, self._info.digits)
            if request.type == "stop_limit":
                if request.limit_price is None:
                    raise InvalidOrderError("stop-limit orders require a limit_price")
                limit_price = round(request.limit_price, self._info.digits)
                _validate_stop_limit(request.side, price, limit_price)
            _validate_sl_tp(request.side, price, request.sl, request.tp)
        else:
            price = None
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
            created_at=self._candle.ts if self._candle else datetime.now(UTC),
            limit_price=limit_price,
        )
        self._orders[order.id] = order
        if request.type == "market":
            self._open_fill_ids.append(order.id)
        return order

    def cancel_order(self, order_id: str) -> BrokerOrder:
        order = self._orders.get(order_id)
        if order is None:
            raise UnknownRefError(f"unknown order: {order_id}")
        if order.state != "pending":
            raise InvalidOrderError(f"cannot cancel order in state {order.state}")
        cancelled = _replace(order, state="cancelled")
        self._orders[order_id] = cancelled
        if self.on_order_update is not None:
            self.on_order_update(cancelled)
        return cancelled

    # -- bars -----------------------------------------------------------------

    def on_bar(self, candle: Candle) -> list[tuple[str, object]]:
        """Advance the replay to ``candle`` and settle orders + protections.

        Market orders queued while processing the previous bar fill at this
        bar's open; pending limit/stop orders and SL/TP/trailing are resolved
        against this bar's OHLC. Returns ``(event, payload)`` pairs.
        """
        self._candle = candle
        events: list[tuple[str, object]] = []

        bid, ask = self._bid_ask(candle.o)
        for oid in self._open_fill_ids:
            order = self._orders.get(oid)
            if order is None or order.state != "pending":
                continue
            mid = ask if order.side == "buy" else bid
            price = self._apply_slippage(order.side, mid)
            filled = self._fill(order, price)
            if filled.state == "filled":
                events.append(("order.filled", filled))
        self._open_fill_ids.clear()

        for oid in list(self._orders):
            order = self._orders[oid]
            if order.symbol != candle.symbol or order.state != "pending":
                continue
            fill = self._intrabar_order_fill(order, candle)
            if fill is None:
                continue
            if order.type == "stop":
                bid, ask = self._bid_ask(fill)
                mid = ask if order.side == "buy" else bid
                price = self._apply_slippage(order.side, mid)
            else:
                price = fill
            filled = self._fill(order, price)
            if filled.state == "filled":
                events.append(("order.filled", filled))

        for pid in list(self._positions):
            position = self._positions[pid]
            if position.symbol != candle.symbol:
                continue
            updated = self._apply_trailing(position, candle)
            if updated is not position:
                self._positions[pid] = updated
                position = updated
            exit_price = self._intrabar_exit(position, candle)
            if exit_price is not None:
                trade = self.close_position(position.id, price=exit_price, at=candle.ts)
                events.append(("position.closed", trade))
        return events

    # -- fills ----------------------------------------------------------------

    def _fill(self, order: BrokerOrder, price: float) -> BrokerOrder:
        fill = round(price, self._info.digits)
        if order.sl is not None or order.tp is not None:
            try:
                _validate_sl_tp(order.side, fill, order.sl, order.tp)
            except InvalidOrderError:
                return self._reject(order)
        if self._config.margin_enabled:
            margin = self.margin_required(order.symbol, order.volume, fill)
            if margin > self._account.balance:
                return self._reject(order)
        notional = fill * self._info.contract_size * order.volume
        commission = round(notional * self._commission_rate, 2)
        filled = _replace(order, state="filled", filled_price=fill)
        self._orders[order.id] = filled
        self._account.balance = round(self._account.balance - commission, 2)
        self._commission_total = round(self._commission_total + commission, 2)
        position = BrokerPosition(
            id=f"p-{filled.id[2:]}",
            symbol=order.symbol,
            side=order.side,
            volume=order.volume,
            open_price=fill,
            sl=order.sl,
            tp=order.tp,
            opened_at=self._candle.ts if self._candle else datetime.now(UTC),
            commission=commission,
            magic=order.magic,
        )
        self._positions[position.id] = position
        self._position_magic[position.id] = order.magic
        if self.on_order_update is not None:
            self.on_order_update(filled)
        return filled

    def _reject(self, order: BrokerOrder) -> BrokerOrder:
        rejected = _replace(order, state="rejected")
        self._orders[order.id] = rejected
        if self.on_order_update is not None:
            self.on_order_update(rejected)
        return rejected

    def _intrabar_order_fill(self, order: BrokerOrder, candle: Candle) -> float | None:
        high, low = candle.h, candle.low
        if order.type == "limit":
            if order.side == "buy" and low <= order.price:
                return order.price
            if order.side == "sell" and high >= order.price:
                return order.price
        elif order.type == "stop":
            if order.side == "buy" and high >= order.price:
                return order.price
            if order.side == "sell" and low <= order.price:
                return order.price
        elif order.type == "stop_limit":
            if order.side == "buy" and high >= order.price and low <= order.limit_price:
                return order.limit_price
            if order.side == "sell" and low <= order.price and high >= order.limit_price:
                return order.limit_price
        return None

    def _intrabar_exit(self, position: BrokerPosition, candle: Candle) -> float | None:
        """Resolve SL/TP for one position against one bar (gap-aware)."""
        open_price, high, low = candle.o, candle.h, candle.low
        sl, tp = position.sl, position.tp
        if position.side == "buy":
            sl_hit = sl is not None and low <= sl
            tp_hit = tp is not None and high >= tp
            if sl_hit and tp_hit:
                return min(sl, open_price) if open_price - sl <= tp - open_price else max(tp, open_price)
            if sl_hit:
                return self._apply_slippage("sell", min(sl, open_price))
            if tp_hit:
                return max(tp, open_price)
        else:
            sl_hit = sl is not None and high >= sl
            tp_hit = tp is not None and low <= tp
            if sl_hit and tp_hit:
                return max(sl, open_price) if sl - open_price <= open_price - tp else min(tp, open_price)
            if sl_hit:
                return self._apply_slippage("buy", max(sl, open_price))
            if tp_hit:
                return min(tp, open_price)
        return None

    def _apply_trailing(self, position: BrokerPosition, candle: Candle) -> BrokerPosition:
        if position.trail is None:
            return position
        trail = round(position.trail, self._info.digits)
        if position.side == "buy":
            extreme = max(position.trail_extreme or position.open_price, candle.h)
            trail_sl = round(extreme - trail, self._info.digits)
            new_sl = trail_sl if position.sl is None else max(position.sl, trail_sl)
        else:
            extreme = min(position.trail_extreme or position.open_price, candle.low)
            trail_sl = round(extreme + trail, self._info.digits)
            new_sl = trail_sl if position.sl is None else min(position.sl, trail_sl)
        if new_sl != position.sl or extreme != position.trail_extreme:
            return _replace_position(position, sl=new_sl, trail_extreme=extreme)
        return position

    def _apply_slippage(self, side: str, price: float) -> float:
        slip = self._config.slippage_points
        if slip <= 0:
            return price
        return round(price + slip if side == "buy" else price - slip, self._info.digits)

    # -- positions / queries --------------------------------------------------

    def close_position(self, position_id: str, price: float | None = None, volume: float | None = None, *, at: datetime | None = None) -> ClosedTrade:
        position = self._positions.get(position_id)
        if position is None:
            raise UnknownRefError(f"unknown position: {position_id}")
        at = at or (self._candle.ts if self._candle else datetime.now(UTC))
        if price is None:
            bid, ask = self._bid_ask(self._candle.c if self._candle else position.open_price)
            close_price = bid if position.side == "buy" else ask
        else:
            close_price = price
        close_price = round(close_price, self._info.digits)
        volume = round(position.volume if volume is None else volume, 4)
        if volume <= 0:
            raise InvalidOrderError("close volume must be positive")
        if volume > position.volume:
            raise InvalidOrderError("cannot close more than the position volume")
        direction = 1.0 if position.side == "buy" else -1.0
        gross = (close_price - position.open_price) * direction * self._info.contract_size * volume
        close_notional = close_price * self._info.contract_size * volume
        close_commission = round(close_notional * self._commission_rate, 2)
        swap = self._swap_for(position, volume, at)
        net = round(gross - close_commission - swap, 2)
        trade = ClosedTrade(
            id=_new_id("t"),
            symbol=position.symbol,
            side=position.side,
            volume=volume,
            open_price=position.open_price,
            close_price=close_price,
            gross_pnl=round(gross, 2),
            net_pnl=net,
            commission=close_commission,
            swap=swap,
            closed_at=at,
        )
        self._account.balance = round(self._account.balance + net, 2)
        self._commission_total = round(self._commission_total + close_commission, 2)
        if volume >= position.volume:
            del self._positions[position_id]
        else:
            self._positions[position_id] = _replace_position(position, volume=round(position.volume - volume, 4))
        self._closed.append(trade)
        self._trade_open[trade.id] = position.opened_at
        return trade

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

    def modify_position(
        self,
        position_id: str,
        *,
        sl: object = _UNSET,
        tp: object = _UNSET,
        trail: object = _UNSET,
    ) -> BrokerPosition:
        position = self._positions.get(position_id)
        if position is None:
            raise UnknownRefError(f"unknown position: {position_id}")
        candle = self._candle
        bid, ask = self._bid_ask(candle.c if candle else position.open_price)
        new_sl = position.sl if sl is _UNSET else sl
        new_tp = position.tp if tp is _UNSET else tp
        new_trail = position.trail if trail is _UNSET else trail
        if new_sl is not None:
            if position.side == "buy" and new_sl >= bid:
                raise InvalidOrderError("buy stop loss must be below the current bid")
            if position.side == "sell" and new_sl <= ask:
                raise InvalidOrderError("sell stop loss must be above the current ask")
        if new_tp is not None:
            if position.side == "buy" and new_tp <= bid:
                raise InvalidOrderError("buy take profit must be above the current bid")
            if position.side == "sell" and new_tp >= ask:
                raise InvalidOrderError("sell take profit must be below the current ask")
        if new_trail is not None and new_trail <= 0:
            raise InvalidOrderError("trail must be a positive distance")
        if trail is not _UNSET and new_trail is not None:
            extreme = bid if position.side == "buy" else ask
        else:
            extreme = position.trail_extreme
        updated = _replace_position(position, sl=new_sl, tp=new_tp, trail=new_trail, trail_extreme=extreme)
        self._positions[position_id] = updated
        return updated

    # -- pnl / margin ---------------------------------------------------------

    def margin_required(self, symbol: str, volume: float, price: float) -> float:
        return price * self._info.contract_size * volume / self._config.leverage

    def margin_used(self) -> float:
        total = 0.0
        for position in self._positions.values():
            candle = self._candle
            price = candle.c if candle else position.open_price
            total += self.margin_required(position.symbol, position.volume, price)
        return round(total, 2)

    def floating_pnl(self, position: BrokerPosition) -> float:
        candle = self._candle
        if candle is None:
            return 0.0
        bid, ask = self._bid_ask(candle.c)
        price = bid if position.side == "buy" else ask
        direction = 1.0 if position.side == "buy" else -1.0
        return (price - position.open_price) * direction * self._info.contract_size * position.volume

    def floating_pnl_total(self) -> float:
        return round(sum(self.floating_pnl(p) for p in self._positions.values()), 2)

    def swap_total(self, at: datetime | None = None) -> float:
        at = at or (self._candle.ts if self._candle else datetime.now(UTC))
        realized = sum(trade.swap for trade in self._closed)
        accrued = sum(self._swap_for(p, p.volume, at) for p in self._positions.values())
        return round(realized + accrued, 2)

    def commission_total(self) -> float:
        return round(self._commission_total, 2)

    def exposure(self) -> float:
        total = 0.0
        for position in self._positions.values():
            candle = self._candle
            price = candle.c if candle else position.open_price
            total += price * self._info.contract_size * position.volume
        return round(total, 2)

    def equity(self, at: datetime | None = None) -> float:
        at = at or (self._candle.ts if self._candle else datetime.now(UTC))
        return round(self._account.balance + self.floating_pnl_total() + self.swap_total(at), 2)

    # -- internals -------------------------------------------------------------

    def _bid_ask(self, price: float) -> tuple[float, float]:
        half = self.spread / 2
        return round(price - half, self._info.digits), round(price + half, self._info.digits)

    def _swap_for(self, position: BrokerPosition, volume: float, at: datetime) -> float:
        if not self._config.swap_enabled:
            return 0.0
        points = SWAP_POINTS_PER_LOT_DAY.get(position.symbol, 0.0)
        days = (at.date() - position.opened_at.date()).days if at > position.opened_at else 0
        return round(points * self._info.pip_value * volume * days, 2)

    def trade_opened_at(self, trade_id: str) -> datetime | None:
        return self._trade_open.get(trade_id)


# ---------------------------------------------------------------------------
# Run + store
# ---------------------------------------------------------------------------


def trade_to_dict(trade: ClosedTrade, broker: BacktestBroker, bar_indexes: dict[str, int] | None = None) -> dict:
    """Serialize a closed trade, including candle bar indices for chart plotting.

    ``bar_indexes`` maps candle timestamps (ISO strings) to their position in
    the replayed series, so the frontend can anchor entry/exit markers to the
    chart without re-matching timestamps. Falls back to ``None`` for trades
    whose timestamps are not in the series.
    """
    opened_ts = (broker.trade_opened_at(trade.id) or trade.closed_at).isoformat()
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
        "opened_at": opened_ts,
        "closed_at": trade.closed_at.isoformat(),
        "open_bar": bar_indexes.get(opened_ts) if bar_indexes else None,
        "close_bar": bar_indexes.get(trade.closed_at.isoformat()) if bar_indexes else None,
        "magic": broker._position_magic.get(trade.id, 0),
    }


def run_backtest(
    *,
    strategy_name: str,
    symbol: str,
    timeframe: str = "H1",
    params: dict | None = None,
    config: BacktestConfig | None = None,
    candles: list[Candle] | None = None,
    provider: MarketDataProvider | None = None,
) -> dict:
    """Replay ``candles`` through a strategy and return a serializable result."""
    config = config or BacktestConfig(symbol=symbol, timeframe=timeframe)
    provider = provider or market_data
    if candles is None:
        candles = provider.candles(symbol, timeframe, config.candle_count, config.end_ts)
        if config.start_ts is not None:
            candles = [c for c in candles if c.ts >= config.start_ts]
    if not candles:
        raise ValueError("no candles to backtest")
    strategy_class = _REGISTRY.get(strategy_name)
    if strategy_class is None:
        raise KeyError(f"unknown strategy: {strategy_name}")

    broker = BacktestBroker(config, candles)
    instance_id = f"bt-{uuid.uuid4().hex[:12]}"
    runner = StrategyRunner(
        instance_id,
        strategy_class(params),
        provider=broker,
        symbol=symbol.upper(),
        magic=next(MagicCounter),
        broker=broker,
        timeframe=timeframe,
    )

    def _forward(order: BrokerOrder) -> None:
        runner.feed_order(order)
        if order.state == "filled":
            try:
                runner.feed_position(broker.position(order.id.replace("o-", "p-")))
            except UnknownRefError:
                pass

    broker.on_order_update = _forward
    started = datetime.now(UTC)
    runner.start()

    curve: list[dict] = []
    for candle in candles:
        broker.on_bar(candle)
        runner.feed_candle(candle)
        curve.append({"ts": candle.ts.isoformat(), "equity": broker.equity(candle.ts)})

    last = candles[-1]
    for position in list(broker.open_positions()):
        broker.close_position(position.id, at=last.ts)

    summary = runner.stop()
    bar_indexes = {candle.ts.isoformat(): i for i, candle in enumerate(candles)}
    trades = [trade_to_dict(t, broker, bar_indexes) for t in broker.closed_trades()]
    metrics = compute_metrics(
        trades,
        curve,
        initial_balance=config.initial_balance,
        timeframe=timeframe,
        end_balance=broker.account().balance,
    )
    return {
        "id": instance_id,
        "strategy": summary["strategy"],
        "symbol": summary["symbol"],
        "timeframe": summary["timeframe"],
        "status": summary["status"],
        "last_error": summary["last_error"],
        "started_at": started,
        "finished_at": datetime.now(UTC),
        "config": config_to_dict(config),
        "metrics": metrics,
        "equity_curve": curve,
        "trades": trades,
    }


class BacktestStore:
    """In-memory, per-user store of completed backtest runs."""

    def __init__(self) -> None:
        self._runs: dict[str, tuple[int, dict]] = {}
        self._lock = threading.Lock()

    def save(self, user_id: int, result: dict) -> dict:
        with self._lock:
            self._runs[result["id"]] = (user_id, result)
        return result

    def get(self, user_id: int, run_id: str) -> dict:
        with self._lock:
            entry = self._runs.get(run_id)
        if entry is None or entry[0] != user_id:
            raise KeyError(run_id)
        return entry[1]

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()


backtest_store = BacktestStore()
