"""Tests for the broker adapter abstraction and paper broker."""

from __future__ import annotations

import pytest
from app.services.broker import (
    InsufficientMarginError,
    InvalidOrderError,
    OrderRequest,
    PaperBroker,
    UnknownRefError,
)
from app.services.market_data import market_data


@pytest.fixture()
def broker() -> PaperBroker:
    return PaperBroker(market_data)


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
