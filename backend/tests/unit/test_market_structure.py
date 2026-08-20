"""Tests for deterministic market-structure detectors (Phase 6 line 1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.services.market_data import Candle
from app.services.market_structure import (
    StructureObject,
    analyze,
    classify_structure,
    detect_bos,
    detect_breakouts_and_retests,
    detect_choch,
    detect_regime_changes,
    detect_swings,
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


def points(prices: list[float]) -> list[tuple[float, float, float, float]]:
    return [(p, p, p, p) for p in prices]


U = points([10, 20, 30, 22, 15, 30, 45, 38, 30, 45, 60])  # clean uptrend: HH + HL
D = points([55, 58, 60, 54, 48, 50, 45, 38, 30, 32, 30])  # clean downtrend: LH + LL
U2 = points([10, 20, 30, 22, 15, 30, 45, 38, 30, 45, 60, 50, 40, 25, 35, 20, 30])
E = points([10, 20, 30, 22, 15, 30, 45, 38, 30, 45, 60]) + [(55, 58, 44, 46)]


# -- swing detection ---------------------------------------------------------


def test_detect_swings_finds_local_extrema() -> None:
    swings = detect_swings(candles(U), left=1, right=1)
    assert [(s.bar_index, s.price, s.kind) for s in swings] == [
        (2, 30.0, "swing_high"),
        (4, 15.0, "swing_low"),
        (6, 45.0, "swing_high"),
        (8, 30.0, "swing_low"),
    ]


def test_detect_swings_requires_confirmation_bars() -> None:
    swings = detect_swings(candles(points([5, 10, 20, 10, 5])), left=1, right=1)
    assert [(s.bar_index, s.kind) for s in swings] == [(2, "swing_high")]
    assert (
        detect_swings(candles(points([20, 15, 5, 15, 20])), left=1, right=1)[0].kind == "swing_low"
    )


def test_detect_swings_rejects_bad_params() -> None:
    with pytest.raises(ValueError):
        detect_swings(candles(U), left=0)
    with pytest.raises(ValueError):
        detect_swings(candles(U), right=-1)


# -- structure labels --------------------------------------------------------


def test_classify_uptrend_marks_hh_hl() -> None:
    kinds = [
        s.kind for s in classify_structure(candles(U), detect_swings(candles(U), left=1, right=1))
    ]
    assert kinds == ["swing_high", "swing_low", "hh", "hl"]


def test_classify_downtrend_marks_lh_ll() -> None:
    kinds = [
        s.kind for s in classify_structure(candles(D), detect_swings(candles(D), left=1, right=1))
    ]
    assert kinds == ["swing_high", "swing_low", "lh", "ll", "lh"]


def test_classify_keeps_raw_kind_on_equal_prices() -> None:
    base = candles(U)[0]
    swings = [
        StructureObject(kind="swing_high", bar_index=2, ts=base.ts, price=30.0, timeframe="H1"),
        StructureObject(kind="swing_low", bar_index=4, ts=base.ts, price=20.0, timeframe="H1"),
        StructureObject(
            kind="swing_high", bar_index=6, ts=base.ts, price=30.0, timeframe="H1"
        ),  # equal to prior high
    ]
    structure = classify_structure(candles(U), swings)
    assert structure[-1].kind == "swing_high"  # not hh/lh


# -- BOS / CHoCH -------------------------------------------------------------


def test_bos_bullish_fires_on_cross_of_last_swing_high() -> None:
    events = detect_bos(
        candles(U),
        classify_structure(candles(U), detect_swings(candles(U), left=1, right=1)),
        right=1,
    )
    assert len(events) == 1
    event = events[0]
    assert event.kind == "bos"
    assert event.direction == "bullish"
    assert event.bar_index == 10
    assert event.price == 60.0
    assert event.invalidation_price == 45.0
    assert event.meta["broken_bar"] == 6


def test_bos_fires_once_per_level() -> None:
    events = detect_bos(
        candles(U),
        classify_structure(candles(U), detect_swings(candles(U), left=1, right=1)),
        right=1,
    )
    assert [e.bar_index for e in events] == [10]  # level 45 crossed exactly once


def test_choch_bearish_fires_when_uptrend_low_is_broken() -> None:
    structure = classify_structure(candles(U2), detect_swings(candles(U2), left=1, right=1))
    events = detect_choch(candles(U2), structure, right=1)
    assert [(e.bar_index, e.direction, e.price) for e in events] == [(13, "bearish", 25.0)]
    assert events[0].invalidation_price == 30.0
    assert events[0].meta["broken_bar"] == 8


# -- regime ------------------------------------------------------------------


def test_regime_flips_to_uptrend_after_two_bullish_labels() -> None:
    events = detect_regime_changes(
        candles(U2),
        classify_structure(candles(U2), detect_swings(candles(U2), left=1, right=1)),
        right=1,
    )
    uptrends = [e for e in events if e.direction == "uptrend"]
    assert uptrends
    assert all(e.kind == "regime" and e.status == "active" for e in events)


# -- breakout / retest -------------------------------------------------------


def test_breakout_then_retest_holds() -> None:
    breakouts, retests = detect_breakouts_and_retests(candles(E), min_bars=2, right=1)
    assert [(b.bar_index, b.direction, b.price) for b in breakouts] == [(10, "bullish", 60.0)]
    assert [(r.bar_index, r.direction, r.price, r.meta["breakout_bar"]) for r in retests] == [
        (11, "bullish", 45.0, 10)
    ]
    assert breakouts[0].invalidation_price == 45.0


def test_breakout_invalidated_when_close_returns_through_level() -> None:
    series = points([10, 20, 30, 22, 15, 30, 45, 38, 30, 45, 60, 55, 40, 46])
    breakouts, retests = detect_breakouts_and_retests(candles(series), min_bars=2, right=1)
    assert [b.bar_index for b in breakouts] == [10]
    assert retests == []  # close 40 < 45 invalidated the level before any hold


# -- analyze / determinism ---------------------------------------------------


def test_analyze_serializes_everything() -> None:
    result = analyze(candles(U2), left=1, right=1)
    assert result["symbol"] == "EURUSD"
    assert result["timeframe"] == "H1"
    assert result["candles"] == len(U2)
    for key in ("swings", "bos", "choch", "regimes", "breakouts", "retests"):
        assert key in result
        assert all(
            "bar_index" in obj and "ts" in obj and "price" in obj and "strength" in obj
            for obj in result[key]
        )


def test_analyze_empty_series_is_safe() -> None:
    result = analyze([])
    assert result["candles"] == 0
    assert result["swings"] == [] and result["bos"] == [] and result["retests"] == []


def test_analyze_is_deterministic() -> None:
    first = analyze(candles(E), left=1, right=1, min_bars=2)
    second = analyze(candles(E), left=1, right=1, min_bars=2)
    assert first == second
