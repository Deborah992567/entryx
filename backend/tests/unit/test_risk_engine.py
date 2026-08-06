"""Tests for the UI-independent risk engine."""

from __future__ import annotations

import pytest
from app.services.market_data import market_data
from app.services.risk_engine import RiskEngine, RiskLimits


@pytest.fixture()
def engine() -> RiskEngine:
    return RiskEngine(market_data)


def test_position_size_from_risk_pct(engine: RiskEngine) -> None:
    # EURUSD: contract 100k. Entry 1.10, SL 1.09 -> $1000 loss/lot.
    # 2% of 10k equity = $200 -> 0.2 lots.
    lots = engine.position_size(symbol="EURUSD", equity=10_000, risk_pct=2, entry=1.10, sl=1.09)
    assert lots == pytest.approx(0.2)
    assert lots >= engine.limits.min_lots


def test_position_size_clamped_to_limits(engine: RiskEngine) -> None:
    lots = engine.position_size(symbol="EURUSD", equity=1_000_000, risk_pct=1, entry=1.10, sl=1.099999)
    assert lots == pytest.approx(engine.limits.max_lots_per_order)
    tiny = engine.position_size(symbol="EURUSD", equity=100, risk_pct=0.01, entry=1.10, sl=1.09)
    assert tiny == pytest.approx(engine.limits.min_lots)


def test_position_size_requires_positive_stop_distance(engine: RiskEngine) -> None:
    with pytest.raises(ValueError):
        engine.position_size(symbol="EURUSD", equity=10_000, risk_pct=1, entry=1.10, sl=1.10)


def test_risk_pct_from_lot_size(engine: RiskEngine) -> None:
    # 0.2 lots * $1000/lot loss = $200 on $10k = 2%
    pct = engine.risk_pct(symbol="EURUSD", equity=10_000, entry=1.10, sl=1.09, volume=0.2)
    assert pct == pytest.approx(2.0)


def test_rr_ratio(engine: RiskEngine) -> None:
    assert engine.rr(entry=1.10, sl=1.09, tp=1.13) == pytest.approx(3.0)
    assert engine.rr(entry=1.10, sl=1.09, tp=1.11) == pytest.approx(1.0)
    assert engine.rr(entry=1.10, sl=1.10, tp=1.12) == 0.0


def test_margin_and_margin_level(engine: RiskEngine) -> None:
    info = market_data.symbol_info("EURUSD")
    margin = engine.margin_required(price=1.10, contract_size=info.contract_size, volume=1.0, leverage=100)
    assert margin == pytest.approx(1_100)
    assert engine.margin_level(equity=11_000, margin_used=1_100) == pytest.approx(1_000.0)
    assert engine.margin_level(equity=100, margin_used=0) == 0.0


def test_exposure_value(engine: RiskEngine) -> None:
    info = market_data.symbol_info("EURUSD")
    assert engine.exposure_value(price=1.10, contract_size=info.contract_size, volume=2.0) == pytest.approx(220_000)


def test_assess_returns_full_metrics(engine: RiskEngine) -> None:
    result = engine.assess(symbol="EURUSD", equity=10_000, risk_pct=2, entry=1.10, sl=1.09, tp=1.13)
    assert result["lots"] == pytest.approx(0.2)
    assert result["risk_amount"] == pytest.approx(200.0)
    assert result["risk_pct"] == pytest.approx(2.0)
    assert result["rr"] == pytest.approx(3.0)
    assert result["reward"] == pytest.approx(0.03)
    assert result["margin_required"] == pytest.approx(220.0)
    assert result["exposure"] == pytest.approx(22_000)


def test_validate_order_reports_limit_violations(engine: RiskEngine) -> None:
    errors = engine.validate_order(
        symbol="EURUSD",
        side="buy",
        volume=500,
        entry=1.10,
        sl=1.09,
        equity=10_000,
        free_margin=1_000_000,
        open_positions_count=0,
        open_volume_symbol=0,
    )
    assert any("max lots per order" in e for e in errors)

    errors = engine.validate_order(
        symbol="EURUSD",
        side="buy",
        volume=1.0,
        entry=1.10,
        sl=1.09,
        equity=10_000,
        free_margin=10,
        open_positions_count=60,
        open_volume_symbol=0,
    )
    assert any("max open positions" in e for e in errors)
    assert any("insufficient free margin" in e for e in errors)


def test_validate_order_risk_pct_limit(engine: RiskEngine) -> None:
    errors = engine.validate_order(
        symbol="EURUSD",
        side="buy",
        volume=1.0,
        entry=1.10,
        sl=1.09,
        equity=10_000,
        free_margin=1_000_000,
        open_positions_count=0,
        open_volume_symbol=0,
    )
    assert any("exceeds max risk per trade" in e for e in errors)

    clean = engine.validate_order(
        symbol="EURUSD",
        side="buy",
        volume=0.2,
        entry=1.10,
        sl=1.09,
        equity=10_000,
        free_margin=1_000_000,
        open_positions_count=0,
        open_volume_symbol=0,
    )
    assert clean == []


def test_custom_limits_respected() -> None:
    limits = RiskLimits(max_lots_per_order=1.0, max_open_positions=2, max_risk_pct_per_trade=10.0)
    engine = RiskEngine(market_data, limits)
    assert engine.position_size(symbol="EURUSD", equity=1_000_000, risk_pct=1, entry=1.10, sl=1.099999) == pytest.approx(1.0)
