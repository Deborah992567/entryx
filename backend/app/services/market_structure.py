"""Deterministic market-structure detectors (Phase 6 line 1).

Fully rule-based, input-driven Smart Money Concepts primitives computed over a
closed candle series: swing H/L points, structure labels (HH/HL/LH/LL), Break
of Structure (BOS), Change of Character (CHoCH), trend/range regime, and
breakout/retest. Identical inputs always produce identical outputs — nothing is
random, no indicators are tuned, and every emitted object carries a timestamp,
bar index, price, strength, and (where meaningful) an invalidation level so the
chart renderer can draw and reason about it deterministically.

These detectors are designed for *analysis of a completed series* (chart
annotation, explainer pipelines, scanner). Swing points use right-side
confirmation bars, so the full series must be known before calling them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from app.services.market_data import Candle

# Defaults mirroring the classic fractal swing definition (5 left / 2 right bars).
SWING_LEFT = 5
SWING_RIGHT = 2
# Default window for regime voting and strength/retest lookback.
REGIME_WINDOW = 8
LOOKBACK = 20
# Minimum bars a level must have survived before a break counts as a breakout.
BREAKOUT_MIN_BARS = 10


@dataclass(frozen=True)
class StructureObject:
    """One detected market-structure element (immutable, deterministic).

    ``kind`` is one of: ``swing_high``, ``swing_low``, ``hh``, ``hl``, ``lh``,
    ``ll``, ``bos``, ``choch``, ``regime``, ``breakout``, ``retest``.
    ``direction`` is ``bullish`` / ``bearish`` / ``neutral``.
    ``status`` is ``confirmed`` (needs no further bars) or ``active``.
    """

    kind: str
    bar_index: int
    ts: datetime
    price: float
    timeframe: str
    direction: str = "neutral"
    status: str = "confirmed"
    strength: float = 1.0
    invalidation_price: float | None = None
    meta: dict = field(default_factory=dict)


def structure_to_dict(obj: StructureObject) -> dict:
    return {
        "kind": obj.kind,
        "bar_index": obj.bar_index,
        "ts": obj.ts.isoformat(),
        "price": round(obj.price, 8),
        "timeframe": obj.timeframe,
        "direction": obj.direction,
        "status": obj.status,
        "strength": round(obj.strength, 4),
        "invalidation_price": obj.invalidation_price,
        "meta": obj.meta,
    }


def _swing_strength(candles: list[Candle], i: int, kind: str) -> float:
    """0..1 prominence of a swing relative to its surrounding range."""
    lo = max(0, i - SWING_LEFT)
    hi = min(len(candles), i + SWING_RIGHT + 1)
    span = max(c.h for c in candles[lo:hi]) - min(c.low for c in candles[lo:hi])
    if span <= 0:
        return 1.0
    if kind == "high":
        ratio = (candles[i].h - min(c.low for c in candles[lo:hi])) / span
    else:
        ratio = (max(c.h for c in candles[lo:hi]) - candles[i].low) / span
    return max(0.0, min(1.0, ratio))


def detect_swings(candles: list[Candle], *, left: int = SWING_LEFT, right: int = SWING_RIGHT) -> list[StructureObject]:
    """Find swing highs/lows using left/right fractal confirmation bars."""
    if left < 1 or right < 0:
        raise ValueError("left must be >= 1 and right must be >= 0")
    n = len(candles)
    out: list[StructureObject] = []
    for i in range(left, n - right):
        high_is_swing = all(candles[i].h > candles[j].h for j in range(i - left, i + right + 1) if j != i)
        low_is_swing = all(candles[i].low < candles[j].low for j in range(i - left, i + right + 1) if j != i)
        if high_is_swing:
            out.append(
                StructureObject(
                    kind="swing_high",
                    bar_index=i,
                    ts=candles[i].ts,
                    price=candles[i].h,
                    timeframe=candles[i].timeframe,
                    direction="bullish",
                    strength=_swing_strength(candles, i, "high"),
                )
            )
        if low_is_swing:
            out.append(
                StructureObject(
                    kind="swing_low",
                    bar_index=i,
                    ts=candles[i].ts,
                    price=candles[i].low,
                    timeframe=candles[i].timeframe,
                    direction="bearish",
                    strength=_swing_strength(candles, i, "low"),
                )
            )
    out.sort(key=lambda s: s.bar_index)
    return out


def classify_structure(candles: list[Candle], swings: list[StructureObject] | None = None) -> list[StructureObject]:
    """Label swing sequence as HH/HL/LH/LL.

    The first swing of each polarity stays unlabeled (``swing_high`` /
    ``swing_low``) since there is no prior level to compare against. Subsequent
    swing highs become ``hh`` (higher) or ``lh`` (lower); swing lows become
    ``hl`` (higher) or ``ll`` (lower). Equal prices keep the raw swing kind.
    """
    if swings is None:
        swings = detect_swings(candles)
    out: list[StructureObject] = []
    prev_high: StructureObject | None = None
    prev_low: StructureObject | None = None
    for swing in swings:
        if swing.kind == "swing_high":
            if prev_high is None:
                prev_high = swing
                out.append(swing)
                continue
            if swing.price > prev_high.price:
                labeled = replace(swing, kind="hh", direction="bullish")
            elif swing.price < prev_high.price:
                labeled = replace(swing, kind="lh", direction="bearish")
            else:
                labeled = swing
            prev_high = labeled
            out.append(labeled)
        elif swing.kind == "swing_low":
            if prev_low is None:
                prev_low = swing
                out.append(swing)
                continue
            if swing.price < prev_low.price:
                labeled = replace(swing, kind="ll", direction="bearish")
            elif swing.price > prev_low.price:
                labeled = replace(swing, kind="hl", direction="bullish")
            else:
                labeled = swing
            prev_low = labeled
            out.append(labeled)
    return out
