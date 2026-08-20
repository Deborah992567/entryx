"""Market data provider abstraction plus a deterministic simulated provider.

The provider is a pure-Python in-memory service: candles and quotes are
generated from a seeded random walk so identical calls return identical
results. This keeps tests and the paper broker fully deterministic.
"""

from __future__ import annotations

import math
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

TIMEFRAMES: dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
    "W1": 10080,
    "MN1": 43200,
}


def timeframe_minutes(timeframe: str) -> int:
    minutes = TIMEFRAMES.get(timeframe.upper())
    if minutes is None:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    return minutes


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    ts: datetime
    o: float
    h: float
    low: float
    c: float
    v: float


@dataclass(frozen=True)
class Quote:
    symbol: str
    ts: datetime
    bid: float
    ask: float
    spread: float
    change_pct: float
    volume: float


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    name: str
    category: str
    base_currency: str
    quote_currency: str
    digits: int
    tick_size: float
    contract_size: float
    pip_value: float


class MarketDataProvider(ABC):
    """Interface for any source of market data (simulated or live)."""

    @abstractmethod
    def symbols(self) -> list[SymbolInfo]: ...

    @abstractmethod
    def symbol_info(self, symbol: str) -> SymbolInfo: ...

    @abstractmethod
    def candles(
        self, symbol: str, timeframe: str, count: int, end_ts: datetime | None = None
    ) -> list[Candle]: ...

    @abstractmethod
    def quote(self, symbol: str, at: datetime | None = None) -> Quote: ...


class SimulatedMarketDataProvider(MarketDataProvider):
    """Deterministic, seeded random-walk provider.

    The seed derives from the symbol name, so a given symbol always produces
    the same series. Prices follow a geometric Brownian motion with a fixed
    annualised volatility and a small drift.
    """

    DEFAULT_SYMBOLS: tuple[SymbolInfo, ...] = (
        SymbolInfo("EURUSD", "Euro / US Dollar", "forex", "EUR", "USD", 5, 0.00001, 100_000, 10.0),
        SymbolInfo(
            "GBPUSD", "British Pound / US Dollar", "forex", "GBP", "USD", 5, 0.00001, 100_000, 10.0
        ),
        SymbolInfo(
            "USDJPY", "US Dollar / Japanese Yen", "forex", "USD", "JPY", 3, 0.001, 100_000, 1000.0
        ),
        SymbolInfo(
            "AUDUSD",
            "Australian Dollar / US Dollar",
            "forex",
            "AUD",
            "USD",
            5,
            0.00001,
            100_000,
            10.0,
        ),
        SymbolInfo(
            "USDCAD",
            "US Dollar / Canadian Dollar",
            "forex",
            "USD",
            "CAD",
            5,
            0.00001,
            100_000,
            10.0,
        ),
        SymbolInfo(
            "USDCHF", "US Dollar / Swiss Franc", "forex", "USD", "CHF", 5, 0.00001, 100_000, 10.0
        ),
        SymbolInfo("XAUUSD", "Gold Spot / US Dollar", "commodity", "XAU", "USD", 2, 0.01, 100, 1.0),
        SymbolInfo(
            "XAGUSD", "Silver Spot / US Dollar", "commodity", "XAG", "USD", 3, 0.001, 5000, 5.0
        ),
        SymbolInfo("BTCUSD", "Bitcoin / US Dollar", "crypto", "BTC", "USD", 2, 0.01, 1, 1.0),
        SymbolInfo("ETHUSD", "Ethereum / US Dollar", "crypto", "ETH", "USD", 2, 0.01, 1, 1.0),
        SymbolInfo("US500", "S&P 500 Index", "index", "USD", "USD", 2, 0.1, 50, 5.0),
        SymbolInfo("US30", "Dow Jones Index", "index", "USD", "USD", 1, 1.0, 10, 1.0),
    )

    ANNUAL_VOL = 0.12
    ANNUAL_DRIFT = 0.02
    MINUTES_PER_YEAR = 525_600.0

    def __init__(self) -> None:
        self._infos: dict[str, SymbolInfo] = {s.symbol: s for s in self.DEFAULT_SYMBOLS}
        self._base_price: dict[str, float] = {
            "EURUSD": 1.0850,
            "GBPUSD": 1.2700,
            "USDJPY": 149.50,
            "AUDUSD": 0.6550,
            "USDCAD": 1.3600,
            "USDCHF": 0.8800,
            "XAUUSD": 2350.0,
            "XAGUSD": 28.5,
            "BTCUSD": 67_000.0,
            "ETHUSD": 3_500.0,
            "US500": 5_300.0,
            "US30": 39_000.0,
        }

    # -- MarketDataProvider --------------------------------------------------

    def symbols(self) -> list[SymbolInfo]:
        return list(self.DEFAULT_SYMBOLS)

    def symbol_info(self, symbol: str) -> SymbolInfo:
        try:
            return self._infos[symbol.upper()]
        except KeyError as exc:
            raise KeyError(f"unknown symbol: {symbol}") from exc

    def candles(
        self, symbol: str, timeframe: str, count: int, end_ts: datetime | None = None
    ) -> list[Candle]:
        info = self.symbol_info(symbol)
        tf = timeframe.upper()
        minutes = timeframe_minutes(tf)
        end = _align_down(end_ts or datetime.now(UTC), minutes)
        seed = f"{info.symbol}:{tf}"
        rng = random.Random(seed)
        price = self._base_price[info.symbol] * self._start_factor(rng)
        vol_per_candle = self.ANNUAL_VOL * math.sqrt(minutes / self.MINUTES_PER_YEAR)
        drift_per_candle = self.ANNUAL_DRIFT * (minutes / self.MINUTES_PER_YEAR)
        step = timedelta(minutes=minutes)

        out: list[Candle] = []
        for i in range(count):
            ts = end - step * (count - 1 - i)
            shock = rng.gauss(0, 1)
            close = price * math.exp(drift_per_candle + vol_per_candle * shock)
            high_ext = abs(rng.gauss(0, vol_per_candle / 2))
            low_ext = abs(rng.gauss(0, vol_per_candle / 2))
            candle = Candle(
                symbol=info.symbol,
                timeframe=tf,
                ts=ts,
                o=round(price, info.digits),
                h=round(max(price, close) * (1 + high_ext), info.digits),
                low=round(min(price, close) * (1 - low_ext), info.digits),
                c=round(close, info.digits),
                v=round(rng.uniform(100, 5000), 2),
            )
            out.append(candle)
            price = close
        return out

    def quote(self, symbol: str, at: datetime | None = None) -> Quote:
        info = self.symbol_info(symbol)
        candles = self.candles(symbol, "M1", 2, at)
        last, prev = candles[-1], candles[-2]
        spread = info.tick_size * 2
        change_pct = (last.c / prev.c - 1) * 100
        return Quote(
            symbol=info.symbol,
            ts=last.ts,
            bid=round(last.c - spread / 2, info.digits),
            ask=round(last.c + spread / 2, info.digits),
            spread=spread,
            change_pct=round(change_pct, 4),
            volume=last.v,
        )

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _start_factor(rng: random.Random) -> float:
        return math.exp(rng.gauss(0, 0.05))


def _align_down(dt: datetime, minutes: int) -> datetime:
    minutes = max(1, minutes)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(UTC)
    ts = int(dt.timestamp())
    ts -= ts % (minutes * 60)
    return datetime.fromtimestamp(ts, tz=UTC)


def format_candles(candles: Iterable[Candle]) -> list[dict]:
    return [
        {
            "symbol": c.symbol,
            "timeframe": c.timeframe,
            "ts": c.ts.isoformat(),
            "o": c.o,
            "h": c.h,
            "l": c.low,
            "c": c.c,
            "v": c.v,
        }
        for c in candles
    ]


def format_quote(quote: Quote) -> dict:
    return {
        "symbol": quote.symbol,
        "ts": quote.ts.isoformat(),
        "bid": quote.bid,
        "ask": quote.ask,
        "spread": quote.spread,
        "change_pct": quote.change_pct,
        "volume": quote.volume,
    }


market_data = SimulatedMarketDataProvider()


def next_quote(symbol: str) -> Quote:
    """Tiny jitter on top of the deterministic series for live-tick feel."""
    quote = market_data.quote(symbol)
    rng = random.Random(symbol + ":" + str(int(time.time() // 60)))
    info = market_data.symbol_info(symbol)
    jitter = rng.gauss(0, info.tick_size * 4)
    return Quote(
        symbol=quote.symbol,
        ts=quote.ts,
        bid=round(max(0, quote.bid + jitter), info.digits),
        ask=round(max(0, quote.ask + jitter), info.digits),
        spread=quote.spread,
        change_pct=quote.change_pct,
        volume=quote.volume,
    )
