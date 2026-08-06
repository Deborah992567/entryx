"""Tests for the backtester engine (Phase 5 line 2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.services.backtest import (
    BacktestBroker,
    BacktestConfig,
    run_backtest,
)
from app.services.broker import OrderRequest
from app.services.market_data import Candle
from app.services.strategy import Strategy, register_strategy


def candle(ts: datetime, o: float, h: float, low: float, c: float, symbol: str = "EURUSD") -> Candle:
    return Candle(symbol=symbol, timeframe="H1", ts=ts, o=o, h=h, low=low, c=c, v=100.0)


def candles_for(closes: list[tuple[float, float, float, float]], start: datetime) -> list[Candle]:
    return [candle(start + timedelta(hours=i), o, h, low, c) for i, (o, h, low, c) in enumerate(closes)]


def config(**overrides) -> BacktestConfig:
    base: dict = {"symbol": "EURUSD", "timeframe": "H1", "spread_mult": 0.0}
    base.update(overrides)
    return BacktestConfig(**base)


class PlaceFirstBar(Strategy):
    name = "bt_place_first_bar"

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self._done = False
        self._sl = self.params.get("sl")
        self._tp = self.params.get("tp")

    def on_candle(self, candle: Candle) -> None:
        if not self._done:
            self._done = True
            self.context.place_order(
                OrderRequest(
                    symbol=self.context.symbol,
                    side=self.params.get("side", "buy"),
                    type="market",
                    volume=0.1,
                    sl=self._sl,
                    tp=self._tp,
                )
            )


class PlaceTrail(Strategy):
    name = "bt_place_trail"

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self._step = 0

    def on_candle(self, candle: Candle) -> None:
        self._step += 1
        if self._step == 1:
            self.context.place_order(
                OrderRequest(symbol=self.context.symbol, side="buy", type="market", volume=0.1)
            )
        elif self._step == 2:
            for position in self.context.positions:
                self.context.broker.modify_position(position.id, trail=self.params.get("trail", 1.0))


class HugeOrder(Strategy):
    name = "bt_huge_order"

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self._done = False

    def on_candle(self, candle: Candle) -> None:
        if not self._done:
            self._done = True
            self.context.place_order(
                OrderRequest(symbol=self.context.symbol, side="buy", type="market", volume=100_000)
            )


register_strategy(PlaceFirstBar)
register_strategy(PlaceTrail)
register_strategy(HugeOrder)


# -- run-level replay --------------------------------------------------------


def test_market_order_fills_at_next_bar_open() -> None:
    series = candles_for(
        [(100.0, 100.5, 99.5, 100.0), (100.0, 100.5, 99.5, 100.0), (101.0, 101.5, 100.5, 101.0), (100.0, 100.5, 99.5, 100.0)],
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = run_backtest(
        strategy_name="bt_place_first_bar",
        symbol="EURUSD",
        candles=series,
        config=config(),
    )
    assert result["status"] == "stopped"
    assert len(result["trades"]) == 1
    trade = result["trades"][0]
    assert trade["open_price"] == pytest.approx(series[1].o)  # fill at second bar open
    assert trade["closed_at"] == series[-1].ts.isoformat()


def test_equity_curve_has_one_point_per_bar() -> None:
    series = candles_for(
        [(100.0, 100.5, 99.5, 100.0)] * 12,
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = run_backtest(strategy_name="bt_place_first_bar", symbol="EURUSD", candles=series, config=config())
    assert len(result["equity_curve"]) == len(series)
    assert result["equity_curve"][0]["equity"] == pytest.approx(100_000.0)
    assert result["metrics"]["total_trades"] == 1
    for key in ("win_rate", "profit_factor", "expectancy", "max_drawdown", "max_drawdown_pct", "sharpe"):
        assert key in result["metrics"]


def test_run_without_candles_uses_provider() -> None:
    result = run_backtest(
        strategy_name="sma_cross",
        symbol="EURUSD",
        config=config(candle_count=300, initial_balance=10_000),
    )
    assert result["strategy"] == "sma_cross"
    assert len(result["equity_curve"]) == 300
    assert result["metrics"]["start_balance"] == 10_000


def test_unknown_strategy_raises_keyerror() -> None:
    series = candles_for([(100.0, 100.5, 99.5, 100.0)] * 5, datetime(2024, 1, 1, tzinfo=UTC))
    with pytest.raises(KeyError):
        run_backtest(strategy_name="nope", symbol="EURUSD", candles=series, config=config())


def test_empty_series_raises() -> None:
    with pytest.raises(ValueError):
        run_backtest(strategy_name="bt_place_first_bar", symbol="EURUSD", candles=[], config=config())


# -- commission / spread / slippage / margin ---------------------------------


def test_commission_deducted_at_fill_and_close() -> None:
    series = candles_for(
        [(100.0, 100.5, 99.5, 100.0), (100.0, 100.5, 99.5, 100.0), (100.0, 100.5, 99.5, 100.0)],
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = run_backtest(
        strategy_name="bt_place_first_bar",
        symbol="EURUSD",
        candles=series,
        config=config(commission_bps=20.0),
    )
    trade = result["trades"][0]
    notional = 100.0 * 100_000 * 0.1
    per_side = round(notional * 20.0 / 10_000.0, 2)
    assert trade["commission"] == pytest.approx(per_side)
    assert result["metrics"]["end_balance"] == pytest.approx(100_000 - 2 * per_side)


def test_spread_hits_the_ask_on_buy() -> None:
    series = candles_for(
        [(100.0, 100.5, 99.5, 100.0), (100.0, 100.5, 99.5, 100.0), (100.0, 100.5, 99.5, 100.0)],
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = run_backtest(
        strategy_name="bt_place_first_bar",
        symbol="EURUSD",
        candles=series,
        config=config(spread_mult=1.0),
    )
    half = 0.00001  # tick_size * 2 spread, halved
    assert result["trades"][0]["open_price"] == pytest.approx(100.0 + half)


def test_slippage_moves_fill_price_adversely() -> None:
    series = candles_for(
        [(100.0, 100.5, 99.5, 100.0), (100.0, 100.5, 99.5, 100.0), (100.0, 100.5, 99.5, 100.0)],
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = run_backtest(
        strategy_name="bt_place_first_bar",
        symbol="EURUSD",
        candles=series,
        config=config(slippage_points=0.5),
    )
    assert result["trades"][0]["open_price"] == pytest.approx(100.5)


def test_margin_rejects_oversized_order() -> None:
    series = candles_for([(100.0, 100.5, 99.5, 100.0)] * 3, datetime(2024, 1, 1, tzinfo=UTC))
    result = run_backtest(strategy_name="bt_huge_order", symbol="EURUSD", candles=series, config=config())
    assert result["trades"] == []
    assert result["metrics"]["total_trades"] == 0


def test_margin_disabled_allows_oversized_order() -> None:
    series = candles_for([(100.0, 100.5, 99.5, 100.0)] * 3, datetime(2024, 1, 1, tzinfo=UTC))
    result = run_backtest(
        strategy_name="bt_huge_order",
        symbol="EURUSD",
        candles=series,
        config=config(margin_enabled=False),
    )
    assert len(result["trades"]) == 1


# -- SL / TP / trailing ------------------------------------------------------


def test_take_profit_hit_intrabar() -> None:
    series = candles_for(
        [
            (100.0, 100.5, 99.5, 100.0),
            (100.0, 100.5, 99.5, 100.0),
            (104.0, 106.0, 103.5, 105.0),  # TP 105.0 hit
        ],
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = run_backtest(
        strategy_name="bt_place_first_bar",
        symbol="EURUSD",
        candles=series,
        config=config(),
        params={"sl": 99.0, "tp": 105.0},
    )
    trade = result["trades"][0]
    assert trade["close_price"] == pytest.approx(105.0)
    assert trade["net_pnl"] > 0


def test_stop_loss_hit_intrabar_with_slippage() -> None:
    series = candles_for(
        [
            (100.0, 100.5, 99.5, 100.0),
            (100.0, 100.5, 99.5, 100.0),
            (103.0, 103.5, 97.0, 98.0),  # SL 98.0 hit
        ],
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = run_backtest(
        strategy_name="bt_place_first_bar",
        symbol="EURUSD",
        candles=series,
        config=config(slippage_points=0.2),
        params={"sl": 98.0},
    )
    trade = result["trades"][0]
    assert trade["close_price"] == pytest.approx(97.8)  # SL minus slippage
    assert trade["net_pnl"] < 0


def test_both_sl_and_tp_in_same_bar_takes_closer_target() -> None:
    series = candles_for(
        [
            (100.0, 100.5, 99.5, 100.0),
            (100.0, 100.5, 99.5, 100.0),
            (100.0, 103.0, 98.5, 100.0),  # SL 99.2 closer to open than TP 102.0
        ],
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = run_backtest(
        strategy_name="bt_place_first_bar",
        symbol="EURUSD",
        candles=series,
        config=config(),
        params={"sl": 99.2, "tp": 102.0},
    )
    assert result["trades"][0]["close_price"] == pytest.approx(99.2)


def test_trailing_stop_ratchets_then_stops_out() -> None:
    series = candles_for(
        [
            (100.0, 100.0, 100.0, 100.0),
            (100.0, 100.0, 100.0, 100.0),
            (100.0, 100.0, 100.0, 100.0),
            (104.5, 105.0, 104.2, 104.5),  # rally -> trail SL ratchets to 104.0
            (104.5, 104.5, 102.0, 103.0),  # pullback -> SL hit
        ],
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = run_backtest(
        strategy_name="bt_place_trail",
        symbol="EURUSD",
        candles=series,
        config=config(),
        params={"trail": 1.0},
    )
    trade = result["trades"][0]
    assert trade["open_price"] == pytest.approx(series[1].o)
    assert trade["close_price"] == pytest.approx(104.0)


# -- swap --------------------------------------------------------------------


def test_swap_charged_per_utc_rollover() -> None:
    day0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    series = candles_for(
        [(100.0, 100.5, 99.5, 100.0)] * 3,
        day0,
    ) + [
        candle(day0 + timedelta(days=2), 100.0, 100.5, 99.5, 100.0),
    ]
    broker = BacktestBroker(config(swap_enabled=True), series)
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=0.1))
    broker.on_bar(series[0])
    trade = broker.close_position(broker.open_positions()[0].id, at=day0 + timedelta(days=2))
    assert trade.swap == pytest.approx(0.4)  # 0.2 pts * pip 10 * 0.1 lot * 2 days


def test_swap_disabled_is_zero() -> None:
    day0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    series = candles_for([(100.0, 100.5, 99.5, 100.0)] * 3, day0) + [
        candle(day0 + timedelta(days=2), 100.0, 100.5, 99.5, 100.0),
    ]
    broker = BacktestBroker(config(swap_enabled=False), series)
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=0.1))
    broker.on_bar(series[0])
    trade = broker.close_position(broker.open_positions()[0].id, at=day0 + timedelta(days=2))
    assert trade.swap == 0.0


# -- broker unit details -----------------------------------------------------


def test_broker_pending_limit_fills_intrabar() -> None:
    series = candles_for([(100.0, 100.5, 99.5, 100.0)] * 3, datetime(2024, 1, 1, tzinfo=UTC))
    broker = BacktestBroker(config(), series)
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="limit", volume=0.1, price=99.5))
    assert broker.pending_orders()
    events = broker.on_bar(series[0])
    assert events[0][0] == "order.filled"
    assert broker.open_positions()[0].open_price == pytest.approx(99.5)


def test_broker_stop_order_fills_on_breakout() -> None:
    series = candles_for(
        [(100.0, 100.5, 99.5, 100.0), (102.0, 103.0, 101.5, 102.5)],
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    broker = BacktestBroker(config(), series)
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="stop", volume=0.1, price=101.5))
    events = broker.on_bar(series[0])
    assert events == []
    events = broker.on_bar(series[1])
    assert events[0][0] == "order.filled"
    assert broker.open_positions()[0].open_price == pytest.approx(101.5)


def test_broker_equity_tracks_floating_pnl() -> None:
    series = candles_for([(100.0, 100.5, 99.5, 100.0), (102.0, 102.5, 101.5, 102.0)], datetime(2024, 1, 1, tzinfo=UTC))
    broker = BacktestBroker(config(), series)
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1.0))
    broker.on_bar(series[0])
    assert broker.equity(series[0].ts) == pytest.approx(100_000.0 - 2_000.0)  # entry commission deducted
    assert broker.floating_pnl_total() == pytest.approx(0.0)
    broker.on_bar(series[1])
    assert broker.floating_pnl_total() == pytest.approx(200_000.0)  # (102 - 100) * 100k * 1 lot
    assert broker.equity(series[1].ts) == pytest.approx(100_000.0 - 2_000.0 + 200_000.0)
