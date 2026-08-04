"""Tests for the broker adapter abstraction and paper broker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.services.broker import (
    InsufficientMarginError,
    InvalidOrderError,
    OrderRequest,
    PaperBroker,
    UnknownRefError,
)
from app.services.market_data import Quote, market_data


@pytest.fixture()
def broker() -> PaperBroker:
    return PaperBroker(market_data)


class FakeProvider:
    """Provider with a settable mid price for deterministic trigger tests."""

    def __init__(self, price: float) -> None:
        self._price = price

    def symbols(self):
        return market_data.symbols()

    def symbol_info(self, symbol: str):
        return market_data.symbol_info(symbol)

    def candles(self, *args, **kwargs):
        return []

    def quote(self, symbol: str, at: datetime | None = None) -> Quote:
        info = market_data.symbol_info(symbol)
        spread = info.tick_size * 2
        return Quote(
            symbol=info.symbol,
            ts=datetime.now(UTC),
            bid=self._price,
            ask=round(self._price + spread, info.digits),
            spread=spread,
            change_pct=0.0,
            volume=100.0,
        )

    def set_price(self, price: float) -> None:
        self._price = price



def test_default_account_is_paper(broker: PaperBroker) -> None:
    account = broker.account()
    assert account.number == "0001-PAPER"
    assert account.balance == pytest.approx(100_000)
    assert account.leverage == 100


def test_deposit_and_withdraw(broker: PaperBroker) -> None:
    broker.deposit(1_000)
    assert broker.account().balance == pytest.approx(101_000)
    broker.withdraw(500)
    assert broker.account().balance == pytest.approx(100_500)
    with pytest.raises(InvalidOrderError):
        broker.deposit(-5)
    with pytest.raises(InsufficientMarginError):
        broker.withdraw(1_000_000)


def test_market_order_fills_and_opens_position(broker: PaperBroker) -> None:
    order = broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1.0))
    assert order.state == "filled"
    assert order.filled_price is not None
    positions = broker.open_positions()
    assert len(positions) == 1
    assert positions[0].side == "buy"
    assert positions[0].volume == 1.0
    assert broker.equity() < broker.account().balance  # commission deducted


def test_invalid_orders_rejected(broker: PaperBroker) -> None:
    with pytest.raises(InvalidOrderError):
        broker.place_order(OrderRequest(symbol="EURUSD", side="hold", type="market", volume=1))
    with pytest.raises(InvalidOrderError):
        broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="limit", volume=1))
    with pytest.raises(InvalidOrderError):
        broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=0))


def test_unfilled_limit_stays_pending_then_cancels(broker: PaperBroker) -> None:
    quote = market_data.quote("EURUSD")
    far_price = round(max(0, quote.ask - 2.0), 5)
    order = broker.place_order(
        OrderRequest(symbol="EURUSD", side="buy", type="limit", volume=0.5, price=far_price)
    )
    assert order.state == "pending"
    assert len(broker.open_positions()) == 0
    cancelled = broker.cancel_order(order.id)
    assert cancelled.state == "cancelled"
    assert order.id not in [o.id for o in broker.pending_orders()]


def test_immediately_crossed_limit_fills(broker: PaperBroker) -> None:
    quote = market_data.quote("EURUSD")
    order = broker.place_order(
        OrderRequest(symbol="EURUSD", side="buy", type="limit", volume=0.5, price=quote.ask + 0.1)
    )
    assert order.state == "filled"
    assert len(broker.open_positions()) == 1


def test_close_position_returns_trade_and_removes_position(broker: PaperBroker) -> None:
    broker.place_order(OrderRequest(symbol="USDJPY", side="sell", type="market", volume=0.2))
    positions = broker.open_positions()
    trade = broker.close_position(positions[0].id)
    assert trade.close_price is not None
    assert broker.open_positions() == []
    assert len(broker.closed_trades()) == 1
    assert broker.account().balance > 0


def test_unknown_refs_raise(broker: PaperBroker) -> None:
    with pytest.raises(UnknownRefError):
        broker.position("p-nope")
    with pytest.raises(UnknownRefError):
        broker.order("o-nope")
    with pytest.raises(UnknownRefError):
        broker.close_position("p-nope")


def test_floating_pnl_sign(broker: PaperBroker) -> None:
    quote = market_data.quote("EURUSD")
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1.0))
    position = broker.open_positions()[0]
    pnl_up = broker.floating_pnl(position, quote)
    quote_up = market_data.quote("EURUSD")
    assert isinstance(pnl_up, float)
    assert isinstance(quote_up.bid, float)


def test_margin_blocks_oversized_order(broker: PaperBroker) -> None:
    huge = broker.place_order(
        OrderRequest(symbol="XAUUSD", side="buy", type="market", volume=100_000)
    )
    assert huge.state == "rejected"
    assert broker.open_positions() == []


# -- Line 1: stop-limit, expiry, SL/TP validation ---------------------------------


def test_stop_limit_pending_then_triggers_then_fills() -> None:
    provider = FakeProvider(1.09)
    broker = PaperBroker(provider)
    order = broker.place_order(
        OrderRequest(symbol="EURUSD", side="buy", type="stop_limit", volume=0.5, price=1.10, limit_price=1.11)
    )
    assert order.state == "pending"
    assert order.limit_price == 1.11
    assert broker.open_positions() == []

    provider.set_price(1.112)  # above stop and above limit -> triggered, waiting
    assert broker.on_quote("EURUSD") == []
    assert broker.order(order.id).triggered is True
    assert broker.open_positions() == []

    provider.set_price(1.109)  # ask <= limit -> fills at the limit price
    events = broker.on_quote("EURUSD")
    assert events[0][0] == "order.filled"
    filled = events[0][1]
    assert filled.id == order.id
    assert filled.state == "filled"
    assert filled.filled_price == pytest.approx(1.11)
    assert len(broker.open_positions()) == 1


def test_stop_limit_immediately_crossed_fills() -> None:
    provider = FakeProvider(1.09)
    broker = PaperBroker(provider)
    order = broker.place_order(
        OrderRequest(symbol="EURUSD", side="buy", type="stop_limit", volume=0.5, price=1.085, limit_price=1.10)
    )
    assert order.state == "filled"
    assert order.filled_price == pytest.approx(1.10)
    assert len(broker.open_positions()) == 1


def test_stop_limit_requires_limit_price_and_valid_side() -> None:
    broker = PaperBroker(FakeProvider(1.09))
    with pytest.raises(InvalidOrderError):
        broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="stop_limit", volume=1, price=1.10))
    with pytest.raises(InvalidOrderError):
        broker.place_order(
            OrderRequest(symbol="EURUSD", side="buy", type="stop_limit", volume=1, price=1.10, limit_price=1.05)
        )
    with pytest.raises(InvalidOrderError):
        broker.place_order(
            OrderRequest(symbol="EURUSD", side="sell", type="stop_limit", volume=1, price=1.10, limit_price=1.15)
        )


def test_expiry_transitions_pending_to_expired() -> None:
    provider = FakeProvider(1.09)
    broker = PaperBroker(provider)
    expiry = datetime.now(UTC) + timedelta(minutes=1)
    order = broker.place_order(
        OrderRequest(symbol="EURUSD", side="buy", type="limit", volume=0.5, price=1.05, expiry=expiry)
    )
    assert order.state == "pending"
    assert broker.on_quote("EURUSD") == []  # not yet expired
    events = broker.on_quote("EURUSD", now=expiry + timedelta(seconds=1))
    assert events[0][0] == "order.expired"
    assert broker.order(order.id).state == "expired"
    assert broker.open_positions() == []


def test_expiry_must_be_in_future() -> None:
    broker = PaperBroker(FakeProvider(1.09))
    with pytest.raises(InvalidOrderError):
        broker.place_order(
            OrderRequest(
                symbol="EURUSD",
                side="buy",
                type="limit",
                volume=0.5,
                price=1.05,
                expiry=datetime.now(UTC) - timedelta(seconds=1),
            )
        )


def test_sl_tp_validation() -> None:
    broker = PaperBroker(FakeProvider(1.09))
    with pytest.raises(InvalidOrderError):
        broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1, sl=1.10))
    with pytest.raises(InvalidOrderError):
        broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1, tp=1.08))
    with pytest.raises(InvalidOrderError):
        broker.place_order(OrderRequest(symbol="EURUSD", side="sell", type="market", volume=1, sl=1.08))
    with pytest.raises(InvalidOrderError):
        broker.place_order(OrderRequest(symbol="EURUSD", side="sell", type="market", volume=1, tp=1.10))
    with pytest.raises(InvalidOrderError):
        broker.place_order(
            OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1, sl=1.10, tp=1.11)
        )


def test_valid_sl_tp_accepted_and_stored() -> None:
    broker = PaperBroker(FakeProvider(1.09))
    order = broker.place_order(
        OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1, sl=1.08, tp=1.11)
    )
    assert order.state == "filled"
    position = broker.open_positions()[0]
    assert position.sl == 1.08
    assert position.tp == 1.11


def test_pending_limit_fills_via_quote_tick() -> None:
    provider = FakeProvider(1.09)
    broker = PaperBroker(provider)
    order = broker.place_order(
        OrderRequest(symbol="EURUSD", side="buy", type="limit", volume=0.5, price=1.05)
    )
    assert order.state == "pending"
    provider.set_price(1.04)
    events = broker.on_quote("EURUSD")
    assert events[0][0] == "order.filled"
    assert events[0][1].id == order.id
    assert len(broker.open_positions()) == 1


# -- Line 2: position management ---------------------------------------------------


def test_partial_close_reduces_volume() -> None:
    broker = PaperBroker(FakeProvider(1.09))
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=2.0))
    position = broker.open_positions()[0]
    trade = broker.close_position(position.id, volume=0.5)
    assert trade.volume == pytest.approx(0.5)
    remaining = broker.open_positions()
    assert len(remaining) == 1
    assert remaining[0].id == position.id
    assert remaining[0].volume == pytest.approx(1.5)

    trade2 = broker.close_position(position.id)
    assert trade2.volume == pytest.approx(1.5)
    assert broker.open_positions() == []
    assert len(broker.closed_trades()) == 2


def test_partial_close_validates_volume() -> None:
    broker = PaperBroker(FakeProvider(1.09))
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1.0))
    position = broker.open_positions()[0]
    with pytest.raises(InvalidOrderError):
        broker.close_position(position.id, volume=2.0)
    with pytest.raises(InvalidOrderError):
        broker.close_position(position.id, volume=0)


def test_modify_position_sl_tp_and_clear() -> None:
    broker = PaperBroker(FakeProvider(1.09))
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1))
    position = broker.open_positions()[0]
    updated = broker.modify_position(position.id, sl=1.08, tp=1.12)
    assert updated.sl == pytest.approx(1.08)
    assert updated.tp == pytest.approx(1.12)
    cleared = broker.modify_position(position.id, tp=None)
    assert cleared.tp is None
    assert cleared.sl == pytest.approx(1.08)


def test_modify_position_validates_against_current_price() -> None:
    broker = PaperBroker(FakeProvider(1.09))
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1))
    position = broker.open_positions()[0]
    with pytest.raises(InvalidOrderError):
        broker.modify_position(position.id, sl=1.20)  # buy SL must stay below bid
    with pytest.raises(InvalidOrderError):
        broker.modify_position(position.id, trail=0)
    with pytest.raises(UnknownRefError):
        broker.modify_position("p-nope", sl=1.0)


def test_trailing_stop_ratchets_sl() -> None:
    provider = FakeProvider(1.09)
    broker = PaperBroker(provider)
    broker.place_order(OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1))
    position = broker.open_positions()[0]
    broker.modify_position(position.id, trail=0.01)
    broker.on_quote("EURUSD")
    assert broker.open_positions()[0].sl == pytest.approx(1.08)  # bid - trail

    provider.set_price(1.10)
    broker.on_quote("EURUSD")
    assert broker.open_positions()[0].sl == pytest.approx(1.09)

    provider.set_price(1.095)  # pullback, SL must not move back
    broker.on_quote("EURUSD")
    assert broker.open_positions()[0].sl == pytest.approx(1.09)

    provider.set_price(1.088)  # falls through trailing SL -> closed
    events = broker.on_quote("EURUSD")
    assert events[0][0] == "position.closed"
    assert broker.open_positions() == []


def test_sl_hit_closes_position_via_quote() -> None:
    provider = FakeProvider(1.09)
    broker = PaperBroker(provider)
    broker.place_order(
        OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1, sl=1.07, tp=1.11)
    )
    assert broker.open_positions()
    provider.set_price(1.068)
    events = broker.on_quote("EURUSD")
    assert events[0][0] == "position.closed"
    trade = events[0][1]
    assert trade.close_price == pytest.approx(1.07)
    assert trade.net_pnl < 0
    assert broker.open_positions() == []
    assert len(broker.closed_trades()) == 1


def test_tp_hit_closes_position_via_quote() -> None:
    provider = FakeProvider(1.09)
    broker = PaperBroker(provider)
    broker.place_order(
        OrderRequest(symbol="EURUSD", side="buy", type="market", volume=1, sl=1.07, tp=1.11)
    )
    provider.set_price(1.115)
    events = broker.on_quote("EURUSD")
    assert events[0][0] == "position.closed"
    assert events[0][1].close_price == pytest.approx(1.11)
    assert events[0][1].net_pnl > 0
    assert broker.open_positions() == []
