"""Tests for Smart Money Concept object detectors (Phase 6 line 2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.market_data import Candle
from app.services.market_structure import StructureObject
from app.services.smc_objects import (
    analyze_smc,
    detect_breaker_blocks,
    detect_displacement,
    detect_fvg,
    detect_liquidity_pools,
    detect_order_blocks,
    detect_premium_discount,
    detect_sweeps,
)


def candles(
    points: list[tuple[float, float, float, float]], symbol: str = "EURUSD"
) -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        Candle(
            symbol=symbol,
            timeframe="H1",
            ts=start + timedelta(hours=i),
            o=o,
            h=h,
            low=lo,
            c=c,
            v=100.0,
        )
        for i, (o, h, lo, c) in enumerate(points)
    ]


def pin(price: float) -> tuple[float, float, float, float]:
    return (price, price, price, price)


def rng(open_price: float) -> tuple[float, float, float, float]:
    """Candle with a small fixed range for building a quiet baseline."""
    return (open_price, open_price + 1.0, open_price, open_price + 0.5)


# -- FVG ---------------------------------------------------------------------


def test_bullish_fvg_detected_and_marked_filled() -> None:
    series = [pin(10), pin(10), pin(12), (11, 11, 9, 10)]
    fvgs = detect_fvg(candles(series), lookback=10)
    assert len(fvgs) == 1
    gap = fvgs[0]
    assert (gap.kind, gap.direction, gap.bar_index) == ("fvg", "bullish", 2)
    assert (gap.range_low, gap.range_high) == (10.0, 12.0)
    assert gap.status == "filled"  # idx3 low 9 retraced fully through the gap
    assert gap.invalidation_price == 10.0


def test_bearish_fvg_detected() -> None:
    series = [pin(10), pin(10), pin(8), (9, 11, 9, 9.5)]
    fvgs = detect_fvg(candles(series), lookback=10)
    assert len(fvgs) == 1
    gap = fvgs[0]
    assert (gap.direction, gap.bar_index) == ("bearish", 2)
    assert (gap.range_low, gap.range_high) == (8.0, 10.0)


def test_fvg_stays_active_when_not_retraced() -> None:
    series = [pin(10), pin(10), pin(12), (11, 11, 10.5, 10.8)]
    fvgs = detect_fvg(candles(series), lookback=10)
    assert fvgs[0].status == "active"


# -- displacement ------------------------------------------------------------


def test_displacement_detects_impulse_candle() -> None:
    series = [rng(100 + i * 0.1) for i in range(20)]
    series += [(100.5, 107, 100, 106.5)]  # range 7, body 6 vs avg range ~1
    displ = detect_displacement(candles(series), lookback=20, mult=2.0)
    assert len(displ) == 1
    assert (displ[0].direction, displ[0].bar_index) == ("bullish", 20)


def test_no_displacement_in_quiet_market() -> None:
    series = [pin(100 + (i % 3) * 0.1) for i in range(40)]
    assert detect_displacement(candles(series), lookback=20) == []


# -- liquidity pools ---------------------------------------------------------


def test_equal_highs_group_into_eqh_pool() -> None:
    struct = [
        StructureObject(
            kind="swing_high",
            bar_index=5,
            ts=datetime(2024, 1, 1, tzinfo=UTC),
            price=100.0,
            timeframe="H1",
        ),
        StructureObject(
            kind="swing_low",
            bar_index=8,
            ts=datetime(2024, 1, 1, 8, tzinfo=UTC),
            price=95.0,
            timeframe="H1",
        ),
        StructureObject(
            kind="hh",
            bar_index=12,
            ts=datetime(2024, 1, 1, 12, tzinfo=UTC),
            price=100.2,
            timeframe="H1",
        ),
        StructureObject(
            kind="hl",
            bar_index=15,
            ts=datetime(2024, 1, 1, 15, tzinfo=UTC),
            price=96.0,
            timeframe="H1",
        ),
    ]
    pools = detect_liquidity_pools(
        candles([pin(100.0)] * 20), struct, tolerance=0.005, min_touches=2
    )
    eqh = [p for p in pools if p.kind == "eqh"]
    assert len(eqh) == 1
    assert eqh[0].direction == "bearish"
    assert (eqh[0].range_low, eqh[0].range_high) == (100.0, 100.2)
    assert eqh[0].meta["touches"] == [5, 12]
    assert eqh[0].bar_index == 12


def test_isolated_swing_does_not_form_pool() -> None:
    struct = [
        StructureObject(
            kind="swing_high",
            bar_index=5,
            ts=datetime(2024, 1, 1, tzinfo=UTC),
            price=100.0,
            timeframe="H1",
        )
    ]
    assert detect_liquidity_pools(candles([pin(100.0)] * 10), struct, min_touches=2) == []


# -- sweeps ------------------------------------------------------------------


def test_eqh_sweep_pierces_and_closes_back_inside() -> None:
    struct = [
        StructureObject(
            kind="swing_high",
            bar_index=5,
            ts=datetime(2024, 1, 1, tzinfo=UTC),
            price=100.0,
            timeframe="H1",
        ),
        StructureObject(
            kind="hh",
            bar_index=12,
            ts=datetime(2024, 1, 1, 12, tzinfo=UTC),
            price=100.2,
            timeframe="H1",
        ),
    ]
    pools = detect_liquidity_pools(
        candles([pin(100.0)] * 20), struct, tolerance=0.005, min_touches=2
    )
    series = [pin(100.0)] * 13 + [(100.5, 101.5, 99.0, 99.5)]  # h 101.5 > 100.2, close 99.5 < 100.2
    sweeps = detect_sweeps(candles(series), pools)
    assert len(sweeps) == 1
    sweep = sweeps[0]
    assert (sweep.kind, sweep.direction, sweep.bar_index) == ("sweep", "bearish", 13)
    assert (sweep.range_low, sweep.range_high) == (100.2, 101.5)
    assert sweep.meta["pool_kind"] == "eqh"


def test_close_beyond_pool_is_breakout_not_sweep() -> None:
    struct = [
        StructureObject(
            kind="swing_high",
            bar_index=5,
            ts=datetime(2024, 1, 1, tzinfo=UTC),
            price=100.0,
            timeframe="H1",
        ),
        StructureObject(
            kind="hh",
            bar_index=12,
            ts=datetime(2024, 1, 1, 12, tzinfo=UTC),
            price=100.2,
            timeframe="H1",
        ),
    ]
    pools = detect_liquidity_pools(
        candles([pin(100.0)] * 20), struct, tolerance=0.005, min_touches=2
    )
    series = [pin(100.0)] * 13 + [(100.5, 101.5, 100.3, 101.3)]  # closes above the pool
    assert detect_sweeps(candles(series), pools) == []


# -- order blocks ------------------------------------------------------------


def test_bullish_order_block_is_last_bearish_candle_before_displacement() -> None:
    series = [
        pin(100),
        (101, 101.5, 99.5, 99.8),  # idx1 bearish → order block
        (99.8, 100.0, 99.6, 99.9),
        (99.9, 106.0, 99.8, 105.5),  # idx3 bullish displacement
    ]
    displ = detect_displacement(candles(series), lookback=2, mult=2.0)
    blocks = detect_order_blocks(candles(series), displ, lookback=5)
    assert len(blocks) == 1
    block = blocks[0]
    assert (block.direction, block.bar_index) == ("bullish", 1)
    assert (block.range_low, block.range_high) == (99.5, 101.5)
    assert block.invalidation_price == 99.5
    assert block.status == "active"


def test_order_block_invalidated_after_far_boundary_close() -> None:
    series = [
        pin(100),
        (101, 101.5, 99.5, 99.8),
        (99.8, 100.0, 99.6, 99.9),
        (99.9, 106.0, 99.8, 105.5),
        (100.5, 101.0, 95.0, 96.0),  # small candle closing below the block's low
    ]
    displ = detect_displacement(candles(series), lookback=2, mult=2.0)
    blocks = detect_order_blocks(candles(series), displ, lookback=5)
    assert len(blocks) == 1
    assert blocks[0].status == "invalidated"
    assert blocks[0].meta["invalidated_bar"] == 4


def test_breaker_block_forms_after_swept_order_block_reclaimed() -> None:
    series = [
        pin(100),
        (101, 101.5, 99.5, 99.8),
        (99.8, 100.0, 99.6, 99.9),
        (99.9, 106.0, 99.8, 105.5),  # displacement → OB at idx1
        (105.0, 105.5, 95.0, 96.0),  # sweep/invalidate the OB
        (96.0, 103.0, 95.5, 102.0),  # reclaim above the block → breaker
    ]
    displ = detect_displacement(candles(series), lookback=2, mult=2.0)
    blocks = detect_order_blocks(candles(series), displ, lookback=5)
    breakers = detect_breaker_blocks(candles(series), blocks)
    assert len(breakers) == 1
    breaker = breakers[0]
    assert (breaker.kind, breaker.direction, breaker.bar_index) == ("breaker_block", "bullish", 5)
    assert (breaker.range_low, breaker.range_high) == (99.5, 101.5)
    assert breaker.meta["source_order_block"] == 1


# -- premium / discount ------------------------------------------------------


def test_premium_discount_splits_dealing_range_at_midpoint() -> None:
    struct = [
        StructureObject(
            kind="swing_low",
            bar_index=10,
            ts=datetime(2024, 1, 1, 10, tzinfo=UTC),
            price=90.0,
            timeframe="H1",
        ),
        StructureObject(
            kind="swing_high",
            bar_index=14,
            ts=datetime(2024, 1, 1, 14, tzinfo=UTC),
            price=110.0,
            timeframe="H1",
        ),
    ]
    zones = detect_premium_discount(candles([pin(100.0)] * 20), struct)
    by_kind = {z.kind: z for z in zones}
    assert set(by_kind) == {"premium", "discount"}
    assert by_kind["discount"].range_low == 90.0
    assert by_kind["discount"].range_high == 100.0
    assert by_kind["premium"].range_low == 100.0
    assert by_kind["premium"].range_high == 110.0
    assert by_kind["discount"].bar_index == 14  # anchored at the later swing
    assert by_kind["premium"].meta["midpoint"] == 100.0


def test_premium_discount_empty_without_swings() -> None:
    assert detect_premium_discount(candles([pin(100.0)] * 10), []) == []


# -- orchestration -----------------------------------------------------------


def test_analyze_smc_returns_every_detector_and_is_deterministic() -> None:
    series = [pin(100 + (i % 5)) for i in range(40)]
    result = analyze_smc(candles(series), lookback=10)
    assert result["symbol"] == "EURUSD"
    assert result["timeframe"] == "H1"
    assert result["candles"] == 40
    for key in (
        "fvg",
        "displacement",
        "liquidity_pools",
        "sweeps",
        "order_blocks",
        "breaker_blocks",
        "premium_discount",
    ):
        assert key in result
        for obj in result[key]:
            assert {
                "kind",
                "bar_index",
                "ts",
                "timeframe",
                "direction",
                "range_low",
                "range_high",
                "strength",
                "status",
                "invalidation_price",
            } <= set(obj)
    assert analyze_smc(candles(series), lookback=10) == result


def test_analyze_smc_empty_series_is_safe() -> None:
    result = analyze_smc([])
    assert result["candles"] == 0
    assert result["fvg"] == [] and result["premium_discount"] == []
