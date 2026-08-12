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


# ---------------------------------------------------------------------------
# Regime helper shared by BOS / CHoCH
# ---------------------------------------------------------------------------


def _regime_from(last_high: StructureObject | None, last_low: StructureObject | None) -> str:
    """Trend context from the two most recent swing labels."""
    if last_high is None or last_low is None:
        return "range"
    if last_high.kind == "hh" and last_low.kind == "hl":
        return "uptrend"
    if last_high.kind == "lh" and last_low.kind == "ll":
        return "downtrend"
    return "range"


def _break_strength(candles: list[Candle], bar_index: int, level: float, *, lookback: int = LOOKBACK) -> float:
    """0..1 closeness of a break relative to recent average candle range."""
    lo = max(0, bar_index - lookback)
    window = candles[lo:bar_index]
    if not window:
        return 1.0
    avg = sum(max(c.h - c.low, 1e-9) for c in window) / len(window)
    return min(1.0, abs(candles[bar_index].c - level) / avg)


def detect_bos(candles: list[Candle], structure: list[StructureObject] | None = None, *, right: int = SWING_RIGHT) -> list[StructureObject]:
    """Break of Structure — close beyond the last swing in the prevailing trend.

    In an uptrend a close that crosses above the most recent confirmed swing
    high is a bullish BOS (trend continuation); in a downtrend a close below
    the most recent confirmed swing low is a bearish BOS. Only true crossings
    count, so a level fires at most once. A swing is only used once its
    ``right`` confirmation bars are known, so no future bars leak into a break.
    """
    structure = structure or classify_structure(candles)
    out: list[StructureObject] = []
    last_high: StructureObject | None = None
    last_low: StructureObject | None = None
    ptr = 0
    for i in range(1, len(candles)):
        while ptr < len(structure) and structure[ptr].bar_index + right <= i:
            swing = structure[ptr]
            if swing.kind in {"swing_high", "hh", "lh"}:
                last_high = swing
            elif swing.kind in {"swing_low", "hl", "ll"}:
                last_low = swing
            ptr += 1
        context = _regime_from(last_high, last_low)
        bar = candles[i]
        if context == "uptrend" and last_high is not None:
            if candles[i - 1].c <= last_high.price < bar.c:
                out.append(
                    StructureObject(
                        kind="bos",
                        bar_index=i,
                        ts=bar.ts,
                        price=bar.c,
                        timeframe=bar.timeframe,
                        direction="bullish",
                        strength=_break_strength(candles, i, last_high.price),
                        invalidation_price=last_high.price,
                        meta={
                            "broken": last_high.kind,
                            "broken_price": last_high.price,
                            "broken_bar": last_high.bar_index,
                        },
                    )
                )
        elif context == "downtrend" and last_low is not None:
            if candles[i - 1].c >= last_low.price > bar.c:
                out.append(
                    StructureObject(
                        kind="bos",
                        bar_index=i,
                        ts=bar.ts,
                        price=bar.c,
                        timeframe=bar.timeframe,
                        direction="bearish",
                        strength=_break_strength(candles, i, last_low.price),
                        invalidation_price=last_low.price,
                        meta={
                            "broken": last_low.kind,
                            "broken_price": last_low.price,
                            "broken_bar": last_low.bar_index,
                        },
                    )
                )
    return out


def detect_choch(candles: list[Candle], structure: list[StructureObject] | None = None, *, right: int = SWING_RIGHT) -> list[StructureObject]:
    """Change of Character — close against the prevailing trend's structure.

    In an uptrend a close that crosses below the most recent confirmed swing
    low (turning the HH/HL sequence) is a bearish CHoCH; in a downtrend a close
    above the most recent confirmed swing high is a bullish CHoCH. Unlike BOS,
    CHoCH breaks the *counter* level and signals a possible trend change. Like
    BOS, only confirmation-complete swings are used.
    """
    structure = structure or classify_structure(candles)
    out: list[StructureObject] = []
    last_high: StructureObject | None = None
    last_low: StructureObject | None = None
    ptr = 0
    for i in range(1, len(candles)):
        while ptr < len(structure) and structure[ptr].bar_index + right <= i:
            swing = structure[ptr]
            if swing.kind in {"swing_high", "hh", "lh"}:
                last_high = swing
            elif swing.kind in {"swing_low", "hl", "ll"}:
                last_low = swing
            ptr += 1
        context = _regime_from(last_high, last_low)
        bar = candles[i]
        if context == "uptrend" and last_low is not None:
            if candles[i - 1].c >= last_low.price > bar.c:
                out.append(
                    StructureObject(
                        kind="choch",
                        bar_index=i,
                        ts=bar.ts,
                        price=bar.c,
                        timeframe=bar.timeframe,
                        direction="bearish",
                        strength=_break_strength(candles, i, last_low.price),
                        invalidation_price=last_low.price,
                        meta={
                            "broken": last_low.kind,
                            "broken_price": last_low.price,
                            "broken_bar": last_low.bar_index,
                        },
                    )
                )
        elif context == "downtrend" and last_high is not None:
            if candles[i - 1].c <= last_high.price < bar.c:
                out.append(
                    StructureObject(
                        kind="choch",
                        bar_index=i,
                        ts=bar.ts,
                        price=bar.c,
                        timeframe=bar.timeframe,
                        direction="bullish",
                        strength=_break_strength(candles, i, last_high.price),
                        invalidation_price=last_high.price,
                        meta={
                            "broken": last_high.kind,
                            "broken_price": last_high.price,
                            "broken_bar": last_high.bar_index,
                        },
                    )
                )
    return out


# ---------------------------------------------------------------------------
# Regime (trend / range)
# ---------------------------------------------------------------------------


def _regime_at(bar_index: int, structure: list[StructureObject], *, window: int = REGIME_WINDOW, right: int = SWING_RIGHT) -> str:
    """Majority vote over the last ``window`` labels confirmed by ``bar_index``."""
    recent = [s for s in structure if s.bar_index + right <= bar_index][-window:]
    bull = sum(1 for s in recent if s.kind in {"hh", "hl"})
    bear = sum(1 for s in recent if s.kind in {"lh", "ll"})
    if bull >= 2 and bull > bear:
        return "uptrend"
    if bear >= 2 and bear > bull:
        return "downtrend"
    return "range"


def detect_regime_changes(candles: list[Candle], structure: list[StructureObject] | None = None, *, window: int = REGIME_WINDOW, right: int = SWING_RIGHT) -> list[StructureObject]:
    """Emit a ``regime`` object every time the trend/range regime flips."""
    structure = structure or classify_structure(candles)
    out: list[StructureObject] = []
    previous = "range"
    for i, bar in enumerate(candles):
        regime = _regime_at(i, structure, window=window, right=right)
        if regime != previous:
            out.append(
                StructureObject(
                    kind="regime",
                    bar_index=i,
                    ts=bar.ts,
                    price=bar.c,
                    timeframe=bar.timeframe,
                    direction=regime,
                    status="active",
                    meta={"from": previous},
                )
            )
            previous = regime
    return out


# ---------------------------------------------------------------------------
# Breakout + retest
# ---------------------------------------------------------------------------


def detect_breakouts_and_retests(
    candles: list[Candle],
    structure: list[StructureObject] | None = None,
    *,
    min_bars: int = BREAKOUT_MIN_BARS,
    right: int = SWING_RIGHT,
) -> tuple[list[StructureObject], list[StructureObject]]:
    """Breakout of an established level + the retest that validates or kills it.

    A breakout requires a confirmed swing level that has survived ``min_bars``
    candles before a close crosses it. While a breakout is live, a later candle
    that wicks back to the level but closes on the breakout side is a retest;
    a close back through the level invalidates the breakout (nothing further is
    emitted). Returns ``(breakouts, retests)``.
    """
    structure = structure or classify_structure(candles)
    breakouts: list[StructureObject] = []
    retests: list[StructureObject] = []
    last_high: StructureObject | None = None
    last_low: StructureObject | None = None
    active: tuple[str, float, int] | None = None  # (direction, level, breakout_bar)
    ptr = 0
    for i in range(1, len(candles)):
        while ptr < len(structure) and structure[ptr].bar_index + right + min_bars <= i:
            swing = structure[ptr]
            if swing.kind in {"swing_high", "hh", "lh"}:
                last_high = swing
            elif swing.kind in {"swing_low", "hl", "ll"}:
                last_low = swing
            ptr += 1

        bar = candles[i]
        if active is not None:
            direction, level, breakout_bar = active
            if direction == "bullish":
                if bar.c < level:
                    active = None
                elif bar.low <= level < bar.c and i > breakout_bar:
                    retests.append(
                        StructureObject(
                            kind="retest",
                            bar_index=i,
                            ts=bar.ts,
                            price=level,
                            timeframe=bar.timeframe,
                            direction="bullish",
                            status="confirmed",
                            strength=_break_strength(candles, i, level),
                            invalidation_price=level,
                            meta={"breakout_bar": breakout_bar},
                        )
                    )
            else:
                if bar.c > level:
                    active = None
                elif bar.h >= level > bar.c and i > breakout_bar:
                    retests.append(
                        StructureObject(
                            kind="retest",
                            bar_index=i,
                            ts=bar.ts,
                            price=level,
                            timeframe=bar.timeframe,
                            direction="bearish",
                            status="confirmed",
                            strength=_break_strength(candles, i, level),
                            invalidation_price=level,
                            meta={"breakout_bar": breakout_bar},
                        )
                    )

        if last_high is not None and candles[i - 1].c <= last_high.price < bar.c:
            breakouts.append(
                StructureObject(
                    kind="breakout",
                    bar_index=i,
                    ts=bar.ts,
                    price=bar.c,
                    timeframe=bar.timeframe,
                    direction="bullish",
                    strength=_break_strength(candles, i, last_high.price),
                    invalidation_price=last_high.price,
                    meta={"broken": last_high.kind, "broken_price": last_high.price, "broken_bar": last_high.bar_index},
                )
            )
            active = ("bullish", last_high.price, i)
        elif last_low is not None and candles[i - 1].c >= last_low.price > bar.c:
            breakouts.append(
                StructureObject(
                    kind="breakout",
                    bar_index=i,
                    ts=bar.ts,
                    price=bar.c,
                    timeframe=bar.timeframe,
                    direction="bearish",
                    strength=_break_strength(candles, i, last_low.price),
                    invalidation_price=last_low.price,
                    meta={"broken": last_low.kind, "broken_price": last_low.price, "broken_bar": last_low.bar_index},
                )
            )
            active = ("bearish", last_low.price, i)
    return breakouts, retests


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def analyze(candles: list[Candle], *, left: int = SWING_LEFT, right: int = SWING_RIGHT, window: int = REGIME_WINDOW, min_bars: int = BREAKOUT_MIN_BARS) -> dict:
    """Run every detector over ``candles`` and return a serializable summary."""
    if not candles:
        return {"symbol": "", "timeframe": "", "candles": 0, "left": left, "right": right, "swings": [], "bos": [], "choch": [], "regimes": [], "breakouts": [], "retests": []}
    swings = detect_swings(candles, left=left, right=right)
    structure = classify_structure(candles, swings)
    breakouts, retests = detect_breakouts_and_retests(candles, structure, min_bars=min_bars, right=right)
    return {
        "symbol": candles[0].symbol,
        "timeframe": candles[0].timeframe,
        "candles": len(candles),
        "left": left,
        "right": right,
        "swings": [structure_to_dict(s) for s in structure],
        "bos": [structure_to_dict(s) for s in detect_bos(candles, structure, right=right)],
        "choch": [structure_to_dict(s) for s in detect_choch(candles, structure, right=right)],
        "regimes": [structure_to_dict(s) for s in detect_regime_changes(candles, structure, window=window, right=right)],
        "breakouts": [structure_to_dict(s) for s in breakouts],
        "retests": [structure_to_dict(s) for s in retests],
    }
