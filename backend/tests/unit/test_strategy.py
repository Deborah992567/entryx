"""Tests for the UI-independent strategy framework (Phase 5 line 1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.services.broker import PaperBroker
from app.services.market_data import Candle, Quote, market_data
from app.services.strategy import (
    SmaCrossStrategy,
    Strategy,
    StrategyError,
    StrategyRunner,
    register_strategy,
    strategy_engine,
)


def make_quote(symbol: str = "EURUSD", price: float = 1.1) -> Quote:
    return Quote(
        symbol=symbol,
        ts=datetime.now(UTC),
        bid=price,
        ask=price,
        spread=0.0,
        change_pct=0.0,
        volume=100.0,
    )


def candles_for(closes: list[float], symbol: str = "EURUSD", timeframe: str = "H1") -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        Candle(
            symbol=symbol,
            timeframe=timeframe,
            ts=start + timedelta(hours=i),
            o=c,
            h=c,
            low=c,
            c=c,
            v=100.0,
        )
        for i, c in enumerate(closes)
    ]


class FakeProvider:
    """Provider returning canned candles and a fixed quote."""

    def __init__(self, candles: list[Candle], quote: Quote | None = None) -> None:
        self._candles = candles
        self._quote = quote or make_quote(candles[0].symbol if candles else "EURUSD")

    def candles(
        self, symbol: str, timeframe: str, count: int, end_ts: datetime | None = None
    ) -> list[Candle]:
        return self._candles

    def quote(self, symbol: str, at: datetime | None = None) -> Quote:
        return self._quote

    def symbol_info(self, symbol: str):
        return market_data.symbol_info(symbol)


# -- registry / catalog -----------------------------------------------------


def test_catalog_lists_registered_strategies() -> None:
    names = {item["name"] for item in strategy_engine.catalog()}
    assert "sma_cross" in names


def test_register_strategy_requires_name() -> None:
    class NoName(Strategy):  # no name attribute on purpose
        pass

    with pytest.raises(StrategyError):
        register_strategy(NoName)


def test_sma_cross_rejects_bad_params() -> None:
    with pytest.raises(StrategyError):
        SmaCrossStrategy({"fast": 30, "slow": 10})
    with pytest.raises(StrategyError):
        SmaCrossStrategy({"fast": 0, "slow": 10})


def test_engine_start_unknown_strategy_raises_keyerror() -> None:
    provider = FakeProvider([])
    broker = PaperBroker(provider)
    with pytest.raises(KeyError):
        strategy_engine.start(
            user_id=1, name="does_not_exist", symbol="EURUSD", provider=provider, broker=broker
        )


# -- start / summary --------------------------------------------------------


def test_start_runs_warmup_and_returns_summary() -> None:
    provider = FakeProvider(candles_for([100.0] * 8))
    broker = PaperBroker(provider)
    summary = strategy_engine.start(
        user_id=1,
        name="sma_cross",
        symbol="eurusd",
        provider=provider,
        broker=broker,
        params={"fast": 3, "slow": 5},
    )
    assert summary["instance_id"].startswith("st-")
    assert summary["strategy"] == "sma_cross"
    assert summary["symbol"] == "EURUSD"  # uppercased
    assert summary["status"] == "running"
    assert summary["magic"] >= 10_000


def test_two_starts_get_distinct_magic_numbers() -> None:
    provider = FakeProvider(candles_for([100.0] * 8))
    broker = PaperBroker(provider)
    a = strategy_engine.start(
        user_id=1, name="sma_cross", symbol="EURUSD", provider=provider, broker=broker
    )
    b = strategy_engine.start(
        user_id=1, name="sma_cross", symbol="EURUSD", provider=provider, broker=broker
    )
    assert a["magic"] != b["magic"]
    assert a["instance_id"] != b["instance_id"]


def test_instances_are_scoped_per_user() -> None:
    provider = FakeProvider(candles_for([100.0] * 8))
    broker = PaperBroker(provider)
    strategy_engine.start(
        user_id=1, name="sma_cross", symbol="EURUSD", provider=provider, broker=broker
    )
    strategy_engine.start(
        user_id=2, name="sma_cross", symbol="EURUSD", provider=provider, broker=broker
    )
    assert len(strategy_engine.instances(1)) == 1
    assert len(strategy_engine.instances(2)) == 1


def test_stop_returns_summary_and_removes_instance() -> None:
    provider = FakeProvider(candles_for([100.0] * 8))
    broker = PaperBroker(provider)
    summary = strategy_engine.start(
        user_id=1, name="sma_cross", symbol="EURUSD", provider=provider, broker=broker
    )
    stopped = strategy_engine.stop(1, summary["instance_id"])
    assert stopped["status"] == "stopped"
    assert strategy_engine.instances(1) == []
    with pytest.raises(KeyError):
        strategy_engine.stop(1, summary["instance_id"])
    with pytest.raises(KeyError):
        strategy_engine.stop(2, summary["instance_id"])  # another user cannot stop it


def test_clear_empties_engine() -> None:
    provider = FakeProvider(candles_for([100.0] * 8))
    broker = PaperBroker(provider)
    strategy_engine.start(
        user_id=1, name="sma_cross", symbol="EURUSD", provider=provider, broker=broker
    )
    strategy_engine.clear()
    assert strategy_engine.instances(1) == []


# -- behavior: sma_cross ----------------------------------------------------


def test_sma_cross_buy_signal_opens_position() -> None:
    provider = FakeProvider(candles_for([100.0] * 5 + [110.0]))
    broker = PaperBroker(provider)
    summary = strategy_engine.start(
        user_id=1,
        name="sma_cross",
        symbol="EURUSD",
        provider=provider,
        broker=broker,
        params={"fast": 3, "slow": 5, "volume": 0.1},
    )
    assert len(summary["signals_emitted"]) == 1
    assert summary["signals_emitted"][0]["side"] == "buy"
    assert summary["orders_placed"] == 1

    positions = broker.open_positions()
    assert len(positions) == 1
    assert positions[0].side == "buy"
    assert positions[0].magic == summary["magic"]
    assert positions[0].volume == pytest.approx(0.1)


def test_sma_cross_sell_signal_closes_position() -> None:
    closes = [100.0] * 5 + [110.0, 90.0, 80.0]
    provider = FakeProvider(candles_for(closes[:6]))
    broker = PaperBroker(provider)
    summary = strategy_engine.start(
        user_id=1,
        name="sma_cross",
        symbol="EURUSD",
        provider=provider,
        broker=broker,
        params={"fast": 3, "slow": 5},
    )
    assert len(broker.open_positions()) == 1

    runner = strategy_engine._instances[summary["instance_id"]].runner
    for candle in candles_for(closes[6:]):
        runner.feed_candle(candle)
    assert runner.signals[-1].side == "sell"
    assert broker.open_positions() == []
    assert len(broker.closed_trades()) == 1


def test_no_position_when_series_is_flat() -> None:
    provider = FakeProvider(candles_for([100.0] * 10))
    broker = PaperBroker(provider)
    summary = strategy_engine.start(
        user_id=1,
        name="sma_cross",
        symbol="EURUSD",
        provider=provider,
        broker=broker,
        params={"fast": 3, "slow": 5},
    )
    assert summary["signals_emitted"] == []
    assert summary["orders_placed"] == 0
    assert broker.open_positions() == []


# -- lifecycle hooks / guards ------------------------------------------------


class TickCounter(Strategy):
    name = "tick_counter"

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        self.ticks = 0
        self.seen_symbols: list[str] = []

    def on_tick(self, quote: Quote) -> None:
        self.ticks += 1
        self.seen_symbols.append(quote.symbol)


register_strategy(TickCounter)


def test_feed_quote_dispatches_only_to_matching_symbol() -> None:
    eurusd = FakeProvider(candles_for([100.0] * 8), make_quote("EURUSD"))
    xauusd = FakeProvider(candles_for([2350.0] * 8), make_quote("XAUUSD"))
    broker = PaperBroker(eurusd)
    a = strategy_engine.start(
        user_id=1, name="tick_counter", symbol="EURUSD", provider=eurusd, broker=broker
    )
    b = strategy_engine.start(
        user_id=1, name="tick_counter", symbol="XAUUSD", provider=xauusd, broker=broker
    )

    strategy_engine.feed_quote("EURUSD")
    strategy_engine.feed_quote("EURUSD")
    strategy_engine.feed_quote("XAUUSD")

    a_strat = strategy_engine._instances[a["instance_id"]].runner.strategy
    b_strat = strategy_engine._instances[b["instance_id"]].runner.strategy
    assert a_strat.ticks == 3  # warm-up quote + 2 dispatches
    assert b_strat.ticks == 2  # warm-up quote + 1 dispatch


class Boom(TickCounter):
    name = "boom"

    def on_tick(self, quote: Quote) -> None:
        self.ticks += 1
        raise RuntimeError("boom")


register_strategy(Boom)


def test_hook_error_transitions_runner_to_error_without_escaping() -> None:
    provider = FakeProvider(candles_for([100.0] * 8))
    broker = PaperBroker(provider)
    summary = strategy_engine.start(
        user_id=1, name="boom", symbol="EURUSD", provider=provider, broker=broker
    )
    assert summary["status"] == "error"  # warm-up quote already tripped on_tick
    assert "on_tick" in summary["last_error"]
    assert "boom" in summary["last_error"]


def test_errored_runner_does_not_take_down_others() -> None:
    provider = FakeProvider(candles_for([100.0] * 8), make_quote("EURUSD"))
    broker = PaperBroker(provider)
    boom = strategy_engine.start(
        user_id=1, name="boom", symbol="EURUSD", provider=provider, broker=broker
    )
    safe = strategy_engine.start(
        user_id=1, name="tick_counter", symbol="EURUSD", provider=provider, broker=broker
    )
    assert strategy_engine._instances[boom["instance_id"]].runner.status == "error"

    strategy_engine.feed_quote("EURUSD")
    safe_runner = strategy_engine._instances[safe["instance_id"]].runner
    assert safe_runner.status == "running"
    assert safe_runner.strategy.ticks == 2  # warm-up + dispatch
    assert strategy_engine._instances[boom["instance_id"]].runner.strategy.ticks == 1


# -- signal / order plumbing -------------------------------------------------


def test_context_emit_signal_records_signal() -> None:
    provider = FakeProvider(candles_for([100.0] * 5 + [110.0]))
    broker = PaperBroker(provider)
    summary = strategy_engine.start(
        user_id=1,
        name="sma_cross",
        symbol="EURUSD",
        provider=provider,
        broker=broker,
        params={"fast": 3, "slow": 5},
    )
    assert summary["signals_emitted"][0]["symbol"] == "EURUSD"
    assert "ts" in summary["signals_emitted"][0]
    assert "meta" in summary["signals_emitted"][0]


def test_strategy_orders_are_tagged_with_magic_and_comment() -> None:
    provider = FakeProvider(candles_for([100.0] * 5 + [110.0]))
    broker = PaperBroker(provider)
    summary = strategy_engine.start(
        user_id=1,
        name="sma_cross",
        symbol="EURUSD",
        provider=provider,
        broker=broker,
        params={"fast": 3, "slow": 5},
    )
    position = broker.open_positions()[0]
    assert position.magic == summary["magic"]
    assert broker._positions[position.id].id == position.id


def test_stop_on_idle_runner_is_noop() -> None:
    runner = StrategyRunner(
        "st-test",
        SmaCrossStrategy({"fast": 3, "slow": 5}),
        provider=FakeProvider([]),
        symbol="EURUSD",
        magic=10_000,
        broker=PaperBroker(FakeProvider([])),
    )
    assert runner.status == "idle"
    summary = runner.stop()
    assert summary["status"] == "idle"


def test_start_rejects_wrong_state() -> None:
    runner = StrategyRunner(
        "st-test",
        SmaCrossStrategy({"fast": 3, "slow": 5}),
        provider=FakeProvider([]),
        symbol="EURUSD",
        magic=10_000,
        broker=PaperBroker(FakeProvider([])),
    )
    runner.status = "running"
    with pytest.raises(StrategyError):
        runner.start()
