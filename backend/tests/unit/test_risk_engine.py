"""Tests for risk engine edge cases."""

from __future__ import annotations

import pytest

from app.services.market_data import market_data
from app.services.risk_engine import RiskEngine, RiskLimits


@pytest.fixture
def engine() -> RiskEngine:
    return RiskEngine(market_data)


def test_stop_distance_zero_sl() -> None:
    assert RiskEngine.stop_distance(1.1, 1.1) == 0.0


def test_stop_distance_entry_below_sl() -> None:
    assert RiskEngine.stop_distance(1.0, 1.1) == pytest.approx(0.1)


def test_stop_distance_entry_above_sl() -> None:
    assert RiskEngine.stop_distance(1.1, 1.0) == pytest.approx(0.1)


def test_risk_amount_zero_risk_pct() -> None:
    assert RiskEngine.risk_amount(100000, 0.0) == 0.0


def test_risk_amount_full_risk() -> None:
    assert RiskEngine.risk_amount(100000, 100.0) == 100000.0


def test_rr_zero_risk_returns_zero() -> None:
    assert RiskEngine.rr(1.1, 1.1, 1.2) == 0.0


def test_rr_symmetric() -> None:
    assert RiskEngine.rr(1.0, 0.9, 1.1) == 1.0


def test_rr_asymmetric() -> None:
    assert RiskEngine.rr(1.0, 0.9, 1.2) == 2.0


def test_custom_limits() -> None:
    limits = RiskLimits(max_lots_per_order=10.0, min_lots=0.01)
    engine = RiskEngine(market_data, limits)
    assert engine.limits.max_lots_per_order == 10.0
    assert engine.limits.min_lots == 0.01


def test_symbol_info_returns_correct_data(engine: RiskEngine) -> None:
    info = engine.symbol_info("EURUSD")
    assert info.symbol == "EURUSD"
    assert info.digits == 5
    assert info.tick_size == 0.00001
