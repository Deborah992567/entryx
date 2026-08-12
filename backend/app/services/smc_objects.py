"""Smart Money Concept price-object detectors (Phase 6 line 2).

Deterministic, rule-based detectors for the classic SMC objects built on top of
the Phase 6 line 1 structure engine: Fair Value Gaps (FVG), displacement
(impulse candles), equal-high/equal-low liquidity pools (EQH/EQL), liquidity
sweeps, order blocks, breaker blocks, and premium/discount dealing zones.

Every object is immutable and carries the fields the roadmap demands — ``ts``,
``timeframe``, a ``range_low``/``range_high`` price extent, ``strength``,
``status``, and an ``invalidation_price`` — plus ``bar_index`` for chart
anchoring. All rules are input-driven: identical candles in, identical objects
out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.services.market_data import Candle

# Default lookback used to measure "average" candle range for strength scoring.
ATR_LOOKBACK = 20
# A candle must exceed this multiple of the average range to count as displacement.
DISPLACEMENT_MULT = 2.0
# Swing prices within this fraction of each other form an equal-high/low pool.
LIQUIDITY_TOLERANCE = 0.001
# Minimum touches for a pool to be treated as meaningful liquidity.
LIQUIDITY_MIN_TOUCHES = 2


@dataclass(frozen=True)
class SmcObject:
    """One detected Smart Money Concept object (immutable, deterministic).

    ``kind`` is one of: ``fvg``, ``displacement``, ``eqh``, ``eql``,
    ``sweep``, ``order_block``, ``breaker_block``, ``premium``, ``discount``.
    ``status`` is ``active`` (may still be traded), ``filled`` (price entered
    the whole range), or ``invalidated`` (its premise broke).
    """

    kind: str
    bar_index: int
    ts: datetime
    timeframe: str
    direction: str
    range_low: float
    range_high: float
    strength: float = 1.0
    status: str = "active"
    invalidation_price: float | None = None
    meta: dict = field(default_factory=dict)


def smc_to_dict(obj: SmcObject) -> dict:
    return {
        "kind": obj.kind,
        "bar_index": obj.bar_index,
        "ts": obj.ts.isoformat(),
        "timeframe": obj.timeframe,
        "direction": obj.direction,
        "range_low": round(obj.range_low, 8),
        "range_high": round(obj.range_high, 8),
        "strength": round(obj.strength, 4),
        "status": obj.status,
        "invalidation_price": obj.invalidation_price,
        "meta": obj.meta,
    }


def _avg_range(candles: list[Candle], bar_index: int, *, lookback: int = ATR_LOOKBACK) -> float:
    """Mean candle range over the ``lookback`` bars before ``bar_index``."""
    lo = max(0, bar_index - lookback)
    window = candles[lo:bar_index]
    if not window:
        return 0.0
    return sum(c.h - c.low for c in window) / len(window)


# ---------------------------------------------------------------------------
# Fair Value Gap (FVG)
# ---------------------------------------------------------------------------


def detect_fvg(candles: list[Candle], *, lookback: int = ATR_LOOKBACK) -> list[SmcObject]:
    """Three-candle imbalance gaps: prev vs next candle leaving an untraded region.

    A bullish FVG exists when the candle two bars ago ends below the candle one
    bar ago begins (``prev.h < nxt.low``); the gap is ``[prev.h, nxt.low]``.
    A bearish FVG is the mirror (``prev.low > nxt.h``). The gap is later marked
    ``filled`` if price trades fully through it, otherwise it stays ``active``.
    """
    candidates: list[SmcObject] = []
    for i in range(2, len(candles)):
        prev, cur, nxt = candles[i - 2], candles[i - 1], candles[i]
        if prev.h < nxt.low:
            candidates.append(
                SmcObject(
                    kind="fvg",
                    bar_index=i,
                    ts=nxt.ts,
                    timeframe=nxt.timeframe,
                    direction="bullish",
                    range_low=prev.h,
                    range_high=nxt.low,
                    strength=_strength_vs_range(candles, i, nxt.low - prev.h, lookback=lookback),
                    invalidation_price=prev.h,
                    meta={"body": cur.c - cur.o},
                )
            )
        elif prev.low > nxt.h:
            candidates.append(
                SmcObject(
                    kind="fvg",
                    bar_index=i,
                    ts=nxt.ts,
                    timeframe=nxt.timeframe,
                    direction="bearish",
                    range_low=nxt.h,
                    range_high=prev.low,
                    strength=_strength_vs_range(candles, i, prev.low - nxt.h, lookback=lookback),
                    invalidation_price=prev.low,
                    meta={"body": cur.c - cur.o},
                )
            )
    return [gap if not _fvg_filled(candles, gap) else _replaced(gap, status="filled") for gap in candidates]


def _fvg_filled(candles: list[Candle], gap: SmcObject) -> bool:
    """True when price later trades entirely through the gap region."""
    for bar in candles[gap.bar_index + 1 :]:
        if gap.direction == "bullish":
            if bar.low <= gap.range_low:
                return True
        elif bar.h >= gap.range_high:
            return True
    return False


def _replaced(obj: SmcObject, **changes) -> SmcObject:
    """Immutable rebuild with overridable fields (never double-supplies a keyword)."""
    fields = {k: getattr(obj, k) for k in SmcObject.__dataclass_fields__}
    fields.update(changes)
    return SmcObject(**fields)


def _strength_vs_range(candles: list[Candle], bar_index: int, size: float, *, lookback: int) -> float:
    """0..1 size of ``size`` relative to recent average candle range."""
    avg = _avg_range(candles, bar_index, lookback=lookback)
    if avg <= 0:
        return 1.0
    return min(1.0, size / avg)


# ---------------------------------------------------------------------------
# Displacement (impulse)
# ---------------------------------------------------------------------------


def detect_displacement(candles: list[Candle], *, lookback: int = ATR_LOOKBACK, mult: float = DISPLACEMENT_MULT) -> list[SmcObject]:
    """Impulse candles whose range and body both exceed the norm.

    A candle is displacement if its full range is more than ``mult`` times the
    average range and its body makes up a majority of that range — the signature
    of one-sided (institutional) participation, not noise.
    """
    out: list[SmcObject] = []
    for i in range(lookback, len(candles)):
        bar = candles[i]
        avg = _avg_range(candles, i, lookback=lookback)
        span = bar.h - bar.low
        if avg <= 0 or span < mult * avg:
            continue
        body = abs(bar.c - bar.o)
        if body < span * 0.6:
            continue
        direction = "bullish" if bar.c > bar.o else "bearish"
        out.append(
            SmcObject(
                kind="displacement",
                bar_index=i,
                ts=bar.ts,
                timeframe=bar.timeframe,
                direction=direction,
                range_low=bar.low,
                range_high=bar.h,
                strength=min(1.0, span / (mult * avg)),
                meta={"range": span, "body": body},
            )
        )
    return out
