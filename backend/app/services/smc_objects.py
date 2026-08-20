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
from app.services.market_structure import StructureObject, classify_structure

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
    return [
        gap if not _fvg_filled(candles, gap) else _replaced(gap, status="filled")
        for gap in candidates
    ]


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


def _strength_vs_range(
    candles: list[Candle], bar_index: int, size: float, *, lookback: int
) -> float:
    """0..1 size of ``size`` relative to recent average candle range."""
    avg = _avg_range(candles, bar_index, lookback=lookback)
    if avg <= 0:
        return 1.0
    return min(1.0, size / avg)


# ---------------------------------------------------------------------------
# Displacement (impulse)
# ---------------------------------------------------------------------------


def detect_displacement(
    candles: list[Candle], *, lookback: int = ATR_LOOKBACK, mult: float = DISPLACEMENT_MULT
) -> list[SmcObject]:
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


# ---------------------------------------------------------------------------
# Liquidity pools (EQH / EQL) + sweeps
# ---------------------------------------------------------------------------


def detect_liquidity_pools(
    candles: list[Candle],
    structure: list[StructureObject] | None = None,
    *,
    tolerance: float = LIQUIDITY_TOLERANCE,
    min_touches: int = LIQUIDITY_MIN_TOUCHES,
) -> list[SmcObject]:
    """Group near-equal swings into EQH (equal highs) / EQL (equal lows) pools.

    Consecutive swing highs within ``tolerance`` of each other cluster into one
    equal-high pool (resting sell liquidity above); consecutive swing lows into
    an equal-low pool (buy liquidity below). Pools with fewer than
    ``min_touches`` touches are noise and are dropped. The pool's ``range`` is
    the band between its extreme touches.
    """
    structure = structure or classify_structure(candles)
    highs = [s for s in structure if s.kind in {"swing_high", "hh", "lh"}]
    lows = [s for s in structure if s.kind in {"swing_low", "hl", "ll"}]
    pools = [
        *_group_pools(candles, highs, "eqh", tolerance, min_touches),
        *_group_pools(candles, lows, "eql", tolerance, min_touches),
    ]
    pools.sort(key=lambda p: (p.bar_index, p.kind))
    return pools


def _group_pools(
    candles: list[Candle],
    swings: list[StructureObject],
    kind: str,
    tolerance: float,
    min_touches: int,
) -> list[SmcObject]:
    out: list[SmcObject] = []
    group: list[StructureObject] = []
    for swing in swings:
        if (
            not group
            or abs(swing.price - group[0].price) / max(abs(group[0].price), 1e-12) <= tolerance
        ):
            group.append(swing)
            continue
        if len(group) >= min_touches:
            out.append(_pool_object(candles, group, kind))
        group = [swing]
    if len(group) >= min_touches:
        out.append(_pool_object(candles, group, kind))
    return out


def _pool_object(candles: list[Candle], group: list[StructureObject], kind: str) -> SmcObject:
    low = min(s.price for s in group)
    high = max(s.price for s in group)
    last = group[-1]
    touches = [s.bar_index for s in group]
    if kind == "eqh":
        direction, invalidation = (
            "bearish",
            low,
        )  # sell liquidity rests above; below low voids the pool
    else:
        direction, invalidation = "bullish", high
    return SmcObject(
        kind=kind,
        bar_index=last.bar_index,
        ts=last.ts,
        timeframe=last.timeframe,
        direction=direction,
        range_low=low,
        range_high=high,
        strength=min(1.0, len(group) / 3.0),
        invalidation_price=invalidation,
        meta={"touches": touches, "touch_prices": [s.price for s in group]},
    )


def detect_sweeps(
    candles: list[Candle], pools: list[SmcObject] | None = None, *, lookback: int = ATR_LOOKBACK
) -> list[SmcObject]:
    """Liquidity grabs: pierce a pool boundary, then close back inside.

    A sell-side sweep pierces above an EQH pool (taking the resting stops) and
    closes back under its high; a buy-side sweep pierces below an EQL pool and
    closes back above its low. Each pool is monitored until its first pierce —
    a close beyond the boundary is a real breakout, not a sweep.
    """
    pools = pools or detect_liquidity_pools(candles)
    out: list[SmcObject] = []
    for pool in pools:
        for i in range(pool.bar_index + 1, len(candles)):
            bar = candles[i]
            if pool.kind == "eqh" and bar.h > pool.range_high:
                if bar.c < pool.range_high:
                    out.append(
                        SmcObject(
                            kind="sweep",
                            bar_index=i,
                            ts=bar.ts,
                            timeframe=bar.timeframe,
                            direction="bearish",
                            range_low=pool.range_high,
                            range_high=bar.h,
                            strength=_strength_vs_range(
                                candles, i, bar.h - pool.range_high, lookback=lookback
                            ),
                            invalidation_price=pool.range_low,
                            meta={"pool_kind": "eqh", "pool_bar": pool.bar_index},
                        )
                    )
                break
            if pool.kind == "eql" and bar.low < pool.range_low:
                if bar.c > pool.range_low:
                    out.append(
                        SmcObject(
                            kind="sweep",
                            bar_index=i,
                            ts=bar.ts,
                            timeframe=bar.timeframe,
                            direction="bullish",
                            range_low=bar.low,
                            range_high=pool.range_low,
                            strength=_strength_vs_range(
                                candles, i, pool.range_low - bar.low, lookback=lookback
                            ),
                            invalidation_price=pool.range_high,
                            meta={"pool_kind": "eql", "pool_bar": pool.bar_index},
                        )
                    )
                break
    out.sort(key=lambda s: s.bar_index)
    return out


# ---------------------------------------------------------------------------
# Order blocks + breaker blocks
# ---------------------------------------------------------------------------


def detect_order_blocks(
    candles: list[Candle], displacement: list[SmcObject] | None = None, *, lookback: int = 5
) -> list[SmcObject]:
    """Last opposite candle before a displacement that ignites a move.

    For each bullish displacement the order block is the most recent bearish
    candle in the ``lookback`` bars before it (where institutional buying
    reversed selling); the mirror holds for bearish displacements. Blocks are
    deduplicated by origin candle. A block is later marked ``invalidated`` once
    price closes beyond its far boundary.
    """
    displacement = displacement or detect_displacement(candles)
    candidates: dict[tuple[int, str], SmcObject] = {}
    for displ in displacement:
        direction = displ.direction
        origin = _last_opposite_candle(candles, displ.bar_index, direction, lookback)
        if origin is None:
            continue
        bar = candles[origin]
        if direction == "bullish":
            invalidation = bar.low
        else:
            invalidation = bar.h
        key = (origin, direction)
        if key not in candidates or displ.strength > candidates[key].strength:
            candidates[key] = SmcObject(
                kind="order_block",
                bar_index=origin,
                ts=bar.ts,
                timeframe=bar.timeframe,
                direction=direction,
                range_low=bar.low,
                range_high=bar.h,
                strength=displ.strength,
                invalidation_price=invalidation,
                meta={"displacement_bar": displ.bar_index, "body": bar.c - bar.o},
            )
    out = sorted(candidates.values(), key=lambda o: o.bar_index)
    return [_mark_order_block_status(candles, block) for block in out]


def _last_opposite_candle(
    candles: list[Candle], until: int, direction: str, lookback: int
) -> int | None:
    """Index of the most recent candle before ``until`` with opposite direction."""
    for i in range(until - 1, max(-1, until - lookback - 1), -1):
        bar = candles[i]
        if direction == "bullish" and bar.c < bar.o:
            return i
        if direction == "bearish" and bar.c > bar.o:
            return i
    return None


def _mark_order_block_status(candles: list[Candle], block: SmcObject) -> SmcObject:
    """Invalidate a block once a close breaches its far boundary."""
    for bar in candles[block.bar_index + 1 :]:
        if block.direction == "bullish" and bar.c < block.invalidation_price:
            return _replaced(
                block,
                status="invalidated",
                meta={**block.meta, "invalidated_bar": bar_index_of(candles, bar)},
            )
        if block.direction == "bearish" and bar.c > block.invalidation_price:
            return _replaced(
                block,
                status="invalidated",
                meta={**block.meta, "invalidated_bar": bar_index_of(candles, bar)},
            )
    return block


def bar_index_of(candles: list[Candle], target: Candle) -> int:
    """Index of a candle within the series (identity-based; series are small)."""
    for i, bar in enumerate(candles):
        if bar is target:
            return i
    raise ValueError("candle not in series")


def detect_breaker_blocks(
    candles: list[Candle], order_blocks: list[SmcObject] | None = None
) -> list[SmcObject]:
    """Swept order blocks that get reclaimed and become fresh levels.

    When an order block's far boundary is closed through (the block is
    ``invalidated``) and price then re-closes back beyond the opposite boundary,
    the block is repurposed as a breaker block — a reversal magnet where the
    old institutional orders now stand on the other side.
    """
    order_blocks = order_blocks or detect_order_blocks(candles)
    out: list[SmcObject] = []
    for block in order_blocks:
        if block.status != "invalidated":
            continue
        invalidated_bar = block.meta.get("invalidated_bar")
        if not isinstance(invalidated_bar, int):
            continue
        far = block.invalidation_price
        near = block.range_high if block.direction == "bullish" else block.range_low
        for i in range(invalidated_bar + 1, len(candles)):
            bar = candles[i]
            if block.direction == "bullish" and bar.c > near:
                out.append(
                    SmcObject(
                        kind="breaker_block",
                        bar_index=i,
                        ts=bar.ts,
                        timeframe=bar.timeframe,
                        direction="bullish",
                        range_low=block.range_low,
                        range_high=block.range_high,
                        strength=block.strength,
                        invalidation_price=far,
                        meta={"source_order_block": block.bar_index, "swept_at": invalidated_bar},
                    )
                )
                break
            if block.direction == "bearish" and bar.c < near:
                out.append(
                    SmcObject(
                        kind="breaker_block",
                        bar_index=i,
                        ts=bar.ts,
                        timeframe=bar.timeframe,
                        direction="bearish",
                        range_low=block.range_low,
                        range_high=block.range_high,
                        strength=block.strength,
                        invalidation_price=far,
                        meta={"source_order_block": block.bar_index, "swept_at": invalidated_bar},
                    )
                )
                break
    out.sort(key=lambda o: o.bar_index)
    return out


# ---------------------------------------------------------------------------
# Premium / discount dealing zones
# ---------------------------------------------------------------------------


def detect_premium_discount(
    candles: list[Candle], structure: list[StructureObject] | None = None
) -> list[SmcObject]:
    """Split the current dealing range into premium and discount halves.

    The dealing range is the band between the most recent confirmed swing high
    and swing low. Below the midpoint is ``discount`` (where buying is
    favourable); above it is ``premium`` (where selling is favourable). Two zone
    objects are emitted at the later of the two anchor swings.
    """
    structure = structure or classify_structure(candles)
    highs = [s for s in structure if s.kind in {"swing_high", "hh", "lh"}]
    lows = [s for s in structure if s.kind in {"swing_low", "hl", "ll"}]
    if not highs or not lows:
        return []
    sh, sl = highs[-1], lows[-1]
    lo = min(sh.price, sl.price)
    hi = max(sh.price, sl.price)
    mid = (lo + hi) / 2.0
    anchor = sh if sh.bar_index >= sl.bar_index else sl
    common = {
        "timeframe": anchor.timeframe,
        "ts": anchor.ts,
        "bar_index": anchor.bar_index,
        "strength": 1.0,
        "invalidation_price": mid,
        "meta": {
            "dealing_range_low": lo,
            "dealing_range_high": hi,
            "midpoint": mid,
            "swing_high_bar": sh.bar_index,
            "swing_low_bar": sl.bar_index,
        },
    }
    return [
        SmcObject(kind="discount", direction="bullish", range_low=lo, range_high=mid, **common),
        SmcObject(kind="premium", direction="bearish", range_low=mid, range_high=hi, **common),
    ]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def analyze_smc(
    candles: list[Candle],
    *,
    lookback: int = ATR_LOOKBACK,
    mult: float = DISPLACEMENT_MULT,
    tolerance: float = LIQUIDITY_TOLERANCE,
    min_touches: int = LIQUIDITY_MIN_TOUCHES,
) -> dict:
    """Run every SMC object detector and return a serializable summary."""
    if not candles:
        return {
            "symbol": "",
            "timeframe": "",
            "candles": 0,
            "fvg": [],
            "displacement": [],
            "liquidity_pools": [],
            "sweeps": [],
            "order_blocks": [],
            "breaker_blocks": [],
            "premium_discount": [],
        }
    structure = classify_structure(candles)
    displacement = detect_displacement(candles, lookback=lookback, mult=mult)
    pools = detect_liquidity_pools(candles, structure, tolerance=tolerance, min_touches=min_touches)
    order_blocks = detect_order_blocks(candles, displacement)
    return {
        "symbol": candles[0].symbol,
        "timeframe": candles[0].timeframe,
        "candles": len(candles),
        "fvg": [smc_to_dict(o) for o in detect_fvg(candles, lookback=lookback)],
        "displacement": [smc_to_dict(o) for o in displacement],
        "liquidity_pools": [smc_to_dict(o) for o in pools],
        "sweeps": [smc_to_dict(o) for o in detect_sweeps(candles, pools, lookback=lookback)],
        "order_blocks": [smc_to_dict(o) for o in order_blocks],
        "breaker_blocks": [smc_to_dict(o) for o in detect_breaker_blocks(candles, order_blocks)],
        "premium_discount": [smc_to_dict(o) for o in detect_premium_discount(candles, structure)],
    }
