"""Deterministic financial-calc tests for the indicator engine."""

from datetime import datetime

import pytest
from app.services.indicators import (
    adx,
    atr,
    bollinger,
    build_indicator,
    cci,
    ema,
    ichimoku,
    indicator_names,
    macd,
    momentum,
    obv,
    psar,
    roc,
    rsi,
    sma,
    stochastic,
    vwap,
    wma,
)
from app.services.market_data import Candle


def candle(o: float, h: float, low: float, c: float, v: float) -> Candle:
    return Candle(
        symbol="TEST", timeframe="M1", ts=datetime.fromtimestamp(0), o=o, h=h, low=low, c=c, v=v
    )


def assert_none_then(series, expected):
    assert len(series) == len(expected)
    for got, want in zip(series, expected, strict=True):
        if want is None:
            assert got is None
        else:
            assert got == pytest.approx(want, rel=1e-6)


class TestMovingAverages:
    def test_sma(self):
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert_none_then(sma(series, 3), [None, None, 2.0, 3.0, 4.0])

    def test_sma_invalid_period(self):
        with pytest.raises(ValueError):
            sma([1.0, 2.0], 0)

    def test_sma_warmup_longer_than_series(self):
        assert sma([1.0, 2.0], 5) == [None, None]

    def test_ema(self):
        # alpha = 2/4 = 0.5; seed at index 2 = mean(1,2,3) = 2
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert_none_then(ema(series, 3), [None, None, 2.0, 3.0, 4.0])

    def test_ema_constants_tend_to_series(self):
        result = ema([5.0] * 10, 3)
        assert result[-1] == pytest.approx(5.0)

    def test_wma(self):
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        # period 3, divisor 6: idx2=(1+4+9)/6=14/6, idx3=(2+6+12)/6=20/6, idx4=(3+8+15)/6=26/6
        assert_none_then(wma(series, 3), [None, None, 14.0 / 6.0, 20.0 / 6.0, 26.0 / 6.0])


class TestMomentumOscillators:
    def test_rsi_constant_series_is_100(self):
        candles = [candle(10, 10, 10, 10, 100) for _ in range(15)]
        result = rsi(candles, 14)
        assert result[-1] == 100.0
        assert result[0] is None

    def test_rsi_hand_computed(self):
        closes_ = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08]
        candles_ = [candle(c, c, c, c, 1) for c in closes_]
        # Wilder RSI(14) over 10 samples has no valid value (needs > 14 closes)
        result = rsi(candles_, 14)
        assert all(v is None for v in result)

    def test_rsi_up_only_series(self):
        closes_ = list(range(1, 20))
        candles_ = [candle(c, c, c, c, 1) for c in closes_]
        result = rsi(candles_, 14)
        assert result[-1] == 100.0

    def test_macd_structure_and_lengths(self):
        candles_ = [candle(float(i), float(i) + 1, float(i) - 1, float(i), 1.0) for i in range(60)]
        out = macd(candles_)
        assert set(out) == {"macd", "signal", "histogram"}
        for series in out.values():
            assert len(series) == 60
        # histogram = macd - signal
        for i in range(60):
            m, s, h = out["macd"][i], out["signal"][i], out["histogram"][i]
            if m is not None and s is not None:
                assert h == pytest.approx(m - s)
        assert out["macd"][0] is None
        assert out["macd"][-1] is not None

    def test_macd_invalid_periods(self):
        candles_ = [candle(1, 2, 0.5, 1.5, 1) for _ in range(30)]
        with pytest.raises(ValueError):
            macd(candles_, fast=26, slow=12)

    def test_stochastic_bounds(self):
        candles_ = [candle(10 + i, 12 + i, 9 + i, 11 + i, 1) for i in range(30)]
        out = stochastic(candles_)
        assert len(out["k"]) == len(out["d"]) == 30
        for value in out["k"]:
            if value is not None:
                assert 0.0 <= value <= 100.0
        assert out["k"][0] is None

    def test_stochastic_known_high(self):
        # Highest high over window is the current close -> %K = 100
        candles_ = [candle(5, 5 + i, 5, 5 + i, 1) for i in range(5)]
        candles_[-1] = candle(20, 20, 5, 20, 1)
        out = stochastic(candles_, k_period=5, d_period=1)
        assert out["k"][-1] == pytest.approx(100.0)

    def test_cci_flat_series_is_zero(self):
        candles_ = [candle(10, 10, 10, 10, 1) for _ in range(25)]
        out = cci(candles_, 20)
        assert out[-1] == 0.0

    def test_roc(self):
        candles_ = [candle(i, i, i, i, 1) for i in range(1, 10)]
        out = roc(candles_, 3)
        # at index 3: (4-1)/1*100 = 300
        assert out[3] == pytest.approx(300.0)
        assert out[2] is None

    def test_momentum(self):
        candles_ = [candle(i, i, i, i, 1) for i in range(10)]
        out = momentum(candles_, 3)
        assert out[3] == pytest.approx(3.0)
        assert out[2] is None


class TestVolatility:
    def test_atr_hand_computed(self):
        candles_ = [
            candle(10, 11, 9, 10.5, 1),
            candle(10.5, 13, 10.2, 12, 1),
            candle(12, 12.5, 11, 11.5, 1),
            candle(11.5, 12, 10, 10.5, 1),
            candle(10.5, 11, 9, 9.5, 1),
        ]
        # TRs: 2, 2.8, 1.5, 2, 2 ; ATR(3) seed idx2 = 6.3/3 = 2.1
        # then Wilder: idx3 = (2.1*2+2)/3 = 6.2/3, idx4 = (6.2/3*2+2)/3 = 18.4/9
        out = atr(candles_, 3)
        assert_none_then(out, [None, None, 2.1, 6.2 / 3.0, 18.4 / 9.0])

    def test_bollinger_constant_series(self):
        candles_ = [candle(10, 10, 10, 10, 1) for _ in range(25)]
        out = bollinger(candles_, 20, 2.0)
        assert out["mid"][-1] == pytest.approx(10.0)
        assert out["upper"][-1] == pytest.approx(10.0)
        assert out["lower"][-1] == pytest.approx(10.0)


class TestVolume:
    def test_vwap_hand_computed(self):
        candles_ = [
            candle(10, 12, 8, 10, 10),
            candle(11, 13, 9, 11, 10),
        ]
        # tp: 10, 11 -> vwap = (10*10 + 11*10)/20 = 10.5
        out = vwap(candles_)
        assert out[0] == pytest.approx(10.0)
        assert out[1] == pytest.approx(10.5)

    def test_obv(self):
        candles_ = [
            candle(10, 10, 10, 10, 100),
            candle(10, 10, 10, 11, 50),
            candle(10, 10, 10, 9, 20),
            candle(10, 10, 10, 9, 30),
        ]
        out = obv(candles_)
        assert out == [0.0, 50.0, 30.0, 30.0]


class TestDirectional:
    def test_adx_uptrend(self):
        candles_ = [candle(10 + i, 11 + i, 9 + i, 10.5 + i, 1) for i in range(40)]
        out = adx(candles_, 14)
        assert out["adx"][0] is None
        # persistent uptrend -> +DI high, -DI ~0 -> ADX meaningful
        assert out["plus_di"][-1] is not None and out["minus_di"][-1] is not None
        assert out["adx"][-1] is not None
        assert out["plus_di"][-1] > out["minus_di"][-1]

    def test_ichimoku_warmup(self):
        candles_ = [candle(10 + i, 12 + i, 8 + i, 11 + i, 1) for i in range(60)]
        out = ichimoku(candles_)
        assert len(out["tenkan"]) == len(candles_)
        assert out["tenkan"][0] is None
        assert out["tenkan"][-1] is not None
        assert out["kijun"][-1] is not None
        assert out["senkou_a"][-1] is not None
        assert out["senkou_b"][-1] is not None
        assert out["displacement"] == 26

    def test_psar_trend(self):
        candles_ = [
            candle(10, 11, 9, 10.5, 1),
            candle(10.5, 11.5, 10, 11, 1),
            candle(11, 12, 10.5, 11.5, 1),
            candle(11.5, 12.5, 11, 12, 1),
            candle(12, 13, 11.5, 12.5, 1),
        ]
        out = psar(candles_)
        assert out[0] is None
        # in a rally the SAR sits below price
        for i in (1, 2, 3, 4):
            assert out[i] is not None
            assert out[i] < candles_[i].low


class TestRegistry:
    def test_all_indicators_available(self):
        names = indicator_names()
        assert {
            "sma",
            "ema",
            "wma",
            "rsi",
            "macd",
            "stochastic",
            "atr",
            "adx",
            "cci",
            "roc",
            "momentum",
            "bollinger",
            "vwap",
            "obv",
            "ichimoku",
            "psar",
        } <= set(names)

    def test_build_indicator_default(self):
        candles_ = [candle(float(i), float(i) + 1, float(i) - 1, float(i), 1.0) for i in range(30)]
        out = build_indicator("rsi", candles_)
        assert "value" in out and len(out["value"]) == 30

    def test_build_indicator_unknown(self):
        candles_ = [candle(1, 2, 0.5, 1.5, 1) for _ in range(10)]
        with pytest.raises(KeyError):
            build_indicator("nope", candles_)

    def test_build_indicator_override(self):
        candles_ = [candle(float(i), float(i) + 1, float(i) - 1, float(i), 1.0) for i in range(30)]
        out = build_indicator("sma", candles_, period=5)
        assert out["value"][3] is None and out["value"][4] is not None


class TestLengthsAndAlignment:
    def test_all_series_aligned_to_input(self):
        candles_ = [candle(10 + i, 12 + i, 8 + i, 11 + i, 1) for i in range(50)]
        for name in indicator_names():
            out = build_indicator(name, candles_)
            for key, series in out.items():
                if name == "ichimoku" and key in ("displacement", "chikou"):
                    continue
                assert len(series) == len(candles_), (
                    f"{name}.{key} length {len(series)} != {len(candles_)}"
                )
