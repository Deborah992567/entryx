"""Indicator engine.

Every indicator is a pure function over a list of `Candle` and returns one or
more aligned series of `float | None` (None = warmup window). Results are fully
deterministic, which keeps financial-calc tests exact and the local-AI feature
pipeline reproducible.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from app.services.market_data import Candle

Series = list[float | None]

_MISSING = None


# --------------------------------------------------------------------------- helpers


def closes(candles: list[Candle]) -> list[float]:
    return [c.c for c in candles]


def highs(candles: list[Candle]) -> list[float]:
    return [c.h for c in candles]


def lows(candles: list[Candle]) -> list[float]:
    return [c.low for c in candles]


def typical_price(candles: list[Candle]) -> list[float]:
    return [(c.h + c.low + c.c) / 3.0 for c in candles]


def _round(value: float | None, digits: int = 8) -> float | None:
    return None if value is None else round(value, digits)


# --------------------------------------------------------------------------- moving averages


def sma(series: list[float], period: int) -> Series:
    """Simple moving average."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: Series = [_MISSING] * len(series)
    window = 0.0
    for i, value in enumerate(series):
        window += value
        if i >= period:
            window -= series[i - period]
        if i >= period - 1:
            out[i] = _round(window / period)
    return out


def ema(series: list[float], period: int) -> Series:
    """Exponential moving average (seeded with the SMA of the first window)."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: Series = [_MISSING] * len(series)
    if len(series) < period:
        return out
    alpha = 2.0 / (period + 1.0)
    seed = sum(series[:period]) / period
    out[period - 1] = _round(seed)
    for i in range(period, len(series)):
        value = series[i] * alpha + out[i - 1] * (1 - alpha)
        out[i] = _round(value)
    return out


def wma(series: list[float], period: int) -> Series:
    """Weighted moving average (most recent weight = period)."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: Series = [_MISSING] * len(series)
    divisor = period * (period + 1) / 2.0
    for i in range(period - 1, len(series)):
        total = 0.0
        for j in range(period):
            total += series[i - j] * (period - j)
        out[i] = _round(total / divisor)
    return out


# --------------------------------------------------------------------------- momentum / oscillators


def rsi(candles: list[Candle], period: int = 14) -> Series:
    """Relative Strength Index (Wilder smoothing)."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: Series = [_MISSING] * len(candles)
    if len(candles) <= period:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(candles)):
        change = candles[i].c - candles[i - 1].c
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period + 1, len(candles)):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - 100.0 / (1.0 + rs), 4)


def macd(candles: list[Candle], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, Series]:
    """MACD histogram: macd, signal, histogram."""
    if fast >= slow:
        raise ValueError("fast period must be smaller than slow period")
    close_series = closes(candles)
    fast_ema = ema(close_series, fast)
    slow_ema = ema(close_series, slow)
    macd_series: Series = [
        _round(f - s) if f is not None and s is not None else None
        for f, s in zip(fast_ema, slow_ema, strict=True)
    ]
    signal_series = _ema_over(macd_series, signal)
    hist: Series = [
        _round(m - s) if m is not None and s is not None else None
        for m, s in zip(macd_series, signal_series, strict=True)
    ]
    return {"macd": macd_series, "signal": signal_series, "histogram": hist}


def _ema_over(series: Series, period: int) -> Series:
    """EMA over an already-aligned series, seeded with the SMA of its first window."""
    out: Series = [_MISSING] * len(series)
    values = [(i, v) for i, v in enumerate(series) if v is not None]
    if len(values) < period:
        return out
    alpha = 2.0 / (period + 1.0)
    seed = sum(v for _, v in values[:period]) / period
    out[values[period - 1][0]] = _round(seed)
    prev = seed
    for i in range(period, len(values)):
        prev = values[i][1] * alpha + prev * (1 - alpha)
        out[values[i][0]] = _round(prev)
    return out


def stochastic(candles: list[Candle], k_period: int = 14, d_period: int = 3) -> dict[str, Series]:
    """Stochastic %K/%D. %K is smoothed with a `d_period` SMA."""
    raw: Series = [_MISSING] * len(candles)
    for i in range(k_period - 1, len(candles)):
        window = candles[i - k_period + 1 : i + 1]
        high = max(c.h for c in window)
        low = min(c.low for c in window)
        if high == low:
            raw[i] = 50.0
        else:
            raw[i] = _round((candles[i].c - low) / (high - low) * 100.0, 4)
    compact = [v for v in raw if v is not None]
    k_compact = sma(compact, d_period)
    d_compact = sma([v for v in k_compact if v is not None], d_period)
    pad = [None] * (k_period - 1)
    return {"k": pad + k_compact, "d": pad + [None] * (d_period - 1) + d_compact}


def cci(candles: list[Candle], period: int = 20) -> Series:
    """Commodity Channel Index."""
    tp = typical_price(candles)
    sma_tp = sma(tp, period)
    out: Series = [_MISSING] * len(candles)
    for i in range(period - 1, len(candles)):
        base = sma_tp[i]
        if base is None:
            continue
        window = tp[i - period + 1 : i + 1]
        mean_dev = sum(abs(v - base) for v in window) / period
        if mean_dev == 0:
            out[i] = 0.0
        else:
            out[i] = _round((tp[i] - base) / (0.015 * mean_dev), 4)
    return out


def roc(candles: list[Candle], period: int = 12) -> Series:
    """Rate of change (%)."""
    out: Series = [_MISSING] * len(candles)
    for i in range(period, len(candles)):
        prev = candles[i - period].c
        if prev == 0:
            continue
        out[i] = _round((candles[i].c - prev) / prev * 100.0, 4)
    return out


def momentum(candles: list[Candle], period: int = 12) -> Series:
    """Momentum = close - close[period]."""
    out: Series = [_MISSING] * len(candles)
    for i in range(period, len(candles)):
        out[i] = _round(candles[i].c - candles[i - period].c, 8)
    return out


# --------------------------------------------------------------------------- volatility


def atr(candles: list[Candle], period: int = 14) -> Series:
    """Average True Range (Wilder)."""
    out: Series = [_MISSING] * len(candles)
    if len(candles) < period:
        return out
    trs = _true_ranges(candles)
    seed = sum(trs[:period]) / period
    out[period - 1] = _round(seed)
    for i in range(period, len(candles)):
        value = (out[i - 1] * (period - 1) + trs[i]) / period
        out[i] = _round(value)
    return out


def _true_ranges(candles: list[Candle]) -> list[float]:
    trs: list[float] = []
    for i, candle in enumerate(candles):
        if i == 0:
            trs.append(candle.h - candle.low)
        else:
            prev = candles[i - 1].c
            trs.append(max(candle.h - candle.low, abs(candle.h - prev), abs(candle.low - prev)))
    return trs


def bollinger(candles: list[Candle], period: int = 20, mult: float = 2.0) -> dict[str, Series]:
    """Bollinger Bands: mid, upper, lower."""
    mid = sma(closes(candles), period)
    upper: Series = [_MISSING] * len(candles)
    lower: Series = [_MISSING] * len(candles)
    for i in range(period - 1, len(candles)):
        base = mid[i]
        if base is None:
            continue
        window = [c.c for c in candles[i - period + 1 : i + 1]]
        sd = math.sqrt(sum((v - base) ** 2 for v in window) / period)
        upper[i] = _round(base + mult * sd, 8)
        lower[i] = _round(base - mult * sd, 8)
    return {"mid": mid, "upper": upper, "lower": lower}


# --------------------------------------------------------------------------- volume


def vwap(candles: list[Candle]) -> Series:
    """Anchored (cumulative) VWAP of typical price."""
    out: Series = [_MISSING] * len(candles)
    cum_pv = 0.0
    cum_v = 0.0
    for i, candle in enumerate(candles):
        tp = (candle.h + candle.low + candle.c) / 3.0
        cum_pv += tp * candle.v
        cum_v += candle.v
        if cum_v > 0:
            out[i] = _round(cum_pv / cum_v, 8)
    return out


def obv(candles: list[Candle]) -> Series:
    """On-Balance Volume."""
    out: Series = [_MISSING] * len(candles)
    value = 0.0
    for i, candle in enumerate(candles):
        if i == 0:
            out[i] = 0.0
            continue
        if candle.c > candles[i - 1].c:
            value += candle.v
        elif candle.c < candles[i - 1].c:
            value -= candle.v
        out[i] = _round(value, 2)
    return out


# --------------------------------------------------------------------------- directional / complex


def adx(candles: list[Candle], period: int = 14) -> dict[str, Series]:
    """Average Directional Index: adx, plus_di, minus_di (Wilder smoothing)."""
    n = len(candles)
    adx_out: Series = [_MISSING] * n
    plus_di: Series = [_MISSING] * n
    minus_di: Series = [_MISSING] * n
    if n <= period:
        return {"adx": adx_out, "plus_di": plus_di, "minus_di": minus_di}

    trs = _true_ranges(candles)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = candles[i].h - candles[i - 1].h
        down = candles[i - 1].low - candles[i].low
        plus_dm[i] = up if up > down and up > 0 else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0

    atr_w = sum(trs[1 : period + 1]) / period
    plus_w = sum(plus_dm[1 : period + 1]) / period
    minus_w = sum(minus_dm[1 : period + 1]) / period
    plus_di[period] = _di_value(plus_w, atr_w)
    minus_di[period] = _di_value(minus_w, atr_w)

    dx_values: list[float] = []
    for i in range(period + 1, n):
        atr_w = (atr_w * (period - 1) + trs[i]) / period
        plus_w = (plus_w * (period - 1) + plus_dm[i]) / period
        minus_w = (minus_w * (period - 1) + minus_dm[i]) / period
        pd = _di_value(plus_w, atr_w)
        md = _di_value(minus_w, atr_w)
        plus_di[i] = pd
        minus_di[i] = md
        if pd is None or md is None or (pd + md) == 0:
            dx_values.append(0.0)
        else:
            dx_values.append(round(100.0 * abs(pd - md) / (pd + md), 4))

    if len(dx_values) >= period:
        seed = sum(dx_values[:period]) / period
        adx_out[2 * period] = _round(seed, 4)
        for j in range(period, len(dx_values)):
            idx = 2 * period + (j - period)
            adx_out[idx + 1] = _round((adx_out[idx] * (period - 1) + dx_values[j]) / period, 4)
    return {"adx": adx_out, "plus_di": plus_di, "minus_di": minus_di}


def _di_value(dm_sum: float, atr_sum: float) -> float | None:
    if atr_sum == 0:
        return None
    return round(100.0 * dm_sum / atr_sum, 4)


def ichimoku(
    candles: list[Candle],
    tenkan: int = 9,
    kijun: int = 26,
    senkou_b: int = 52,
) -> dict[str, Series]:
    """Ichimoku Cloud. Returns base lines aligned to input (leading warmup as None)."""
    n = len(candles)
    tenkan_line: Series = [_MISSING] * n
    kijun_line: Series = [_MISSING] * n
    senkou_a: Series = [_MISSING] * n
    senkou_b_line: Series = [_MISSING] * n
    chikou: Series = [_MISSING] * n

    for i, candle in enumerate(candles):
        tenkan_line[i] = _midpoint(candles, i, tenkan)
        kijun_line[i] = _midpoint(candles, i, kijun)
        senkou_b_line[i] = _midpoint(candles, i, senkou_b)
        chikou[i] = candle.c  # drawn shifted back `kijun` bars by the renderer

    for i in range(n):
        if tenkan_line[i] is not None and kijun_line[i] is not None:
            senkou_a[i] = _round((tenkan_line[i] + kijun_line[i]) / 2.0, 8)

    return {
        "tenkan": tenkan_line,
        "kijun": kijun_line,
        "senkou_a": senkou_a,
        "senkou_b": senkou_b_line,
        "chikou": chikou,
        "displacement": kijun,
    }


def _midpoint(candles: list[Candle], index: int, period: int) -> float | None:
    if index < period - 1:
        return None
    window = candles[index - period + 1 : index + 1]
    return _round((max(c.h for c in window) + min(c.low for c in window)) / 2.0, 8)


def psar(candles: list[Candle], step: float = 0.02, max_step: float = 0.2) -> Series:
    """Parabolic SAR (bullish/bearish flip handling)."""
    n = len(candles)
    out: Series = [_MISSING] * n
    if n < 2:
        return out
    uptrend = True
    sar = candles[0].low
    ep = candles[0].h
    accel = step
    for i in range(1, n):
        candle = candles[i]
        if uptrend:
            sar = sar + accel * (ep - sar)
            sar = min(sar, candles[i - 1].low, candles[i - 2].low) if i >= 2 else min(sar, candles[i - 1].low)
            if candle.low < sar:
                uptrend = False
                sar = ep
                ep = candle.low
                accel = step
            elif candle.h > ep:
                ep = candle.h
                accel = min(accel + step, max_step)
        else:
            sar = sar + accel * (ep - sar)
            sar = max(sar, candles[i - 1].h, candles[i - 2].h) if i >= 2 else max(sar, candles[i - 1].h)
            if candle.h > sar:
                uptrend = True
                sar = ep
                ep = candle.h
                accel = step
            elif candle.low < ep:
                ep = candle.low
                accel = min(accel + step, max_step)
        out[i] = _round(sar, 8)
    return out


# --------------------------------------------------------------------------- registry


IndicatorFn = Callable[[list[Candle]], dict[str, Series]]


def build_indicator(name: str, candles: list[Candle], **params) -> dict[str, Series]:
    """Run a named indicator with overridable parameters."""
    try:
        fn = _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"unknown indicator: {name}") from exc
    return fn(candles, **params)


_REGISTRY: dict[str, IndicatorFn] = {
    "sma": lambda c, **p: {"value": sma(closes(c), p.get("period", 20))},
    "ema": lambda c, **p: {"value": ema(closes(c), p.get("period", 20))},
    "wma": lambda c, **p: {"value": wma(closes(c), p.get("period", 20))},
    "rsi": lambda c, **p: {"value": rsi(c, p.get("period", 14))},
    "macd": lambda c, **p: macd(c, p.get("fast", 12), p.get("slow", 26), p.get("signal", 9)),
    "stochastic": lambda c, **p: stochastic(c, p.get("k_period", 14), p.get("d_period", 3)),
    "atr": lambda c, **p: {"value": atr(c, p.get("period", 14))},
    "adx": lambda c, **p: adx(c, p.get("period", 14)),
    "cci": lambda c, **p: {"value": cci(c, p.get("period", 20))},
    "roc": lambda c, **p: {"value": roc(c, p.get("period", 12))},
    "momentum": lambda c, **p: {"value": momentum(c, p.get("period", 12))},
    "bollinger": lambda c, **p: bollinger(c, p.get("period", 20), p.get("mult", 2.0)),
    "vwap": lambda c, **p: {"value": vwap(c)},
    "obv": lambda c, **p: {"value": obv(c)},
    "ichimoku": lambda c, **p: ichimoku(c),
    "psar": lambda c, **p: {"value": psar(c)},
}


def indicator_names() -> list[str]:
    return sorted(_REGISTRY)
