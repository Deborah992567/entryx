"""UI-independent risk engine.

Pure, testable helpers for position sizing, risk %, reward/risk ratio,
exposure, margin, and order validation limits. The engine knows nothing
about the UI or transports; it only needs a `MarketDataProvider` for symbol
definitions.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.market_data import MarketDataProvider, SymbolInfo


@dataclass(frozen=True)
class RiskLimits:
    max_lots_per_order: float = 100.0
    max_lots_per_symbol: float = 500.0
    max_open_positions: int = 50
    max_risk_pct_per_trade: float = 5.0
    min_lots: float = 0.01


class RiskEngine:
    def __init__(self, provider: MarketDataProvider, limits: RiskLimits | None = None) -> None:
        self._provider = provider
        self.limits = limits or RiskLimits()

    def symbol_info(self, symbol: str) -> SymbolInfo:
        return self._provider.symbol_info(symbol)

    # -- pure math ----------------------------------------------------------

    @staticmethod
    def stop_distance(entry: float, sl: float) -> float:
        return abs(entry - sl)

    @staticmethod
    def risk_amount(equity: float, risk_pct: float) -> float:
        return round(equity * risk_pct / 100.0, 2)

    @staticmethod
    def rr(entry: float, sl: float, tp: float) -> float:
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        if risk <= 0:
            return 0.0
        return round(reward / risk, 2)

    @staticmethod
    def margin_required(
        price: float, contract_size: float, volume: float, leverage: float
    ) -> float:
        return round(price * contract_size * volume / leverage, 2)

    @staticmethod
    def margin_level(equity: float, margin_used: float) -> float:
        if margin_used <= 0:
            return 0.0
        return round(equity / margin_used * 100, 2)

    @staticmethod
    def exposure_value(price: float, contract_size: float, volume: float) -> float:
        return round(price * contract_size * volume, 2)

    # -- sizing --------------------------------------------------------------

    def loss_per_lot(self, symbol: str, entry: float, sl: float) -> float:
        info = self.symbol_info(symbol)
        return round(self.stop_distance(entry, sl) * info.contract_size, 8)

    def position_size(
        self, *, symbol: str, equity: float, risk_pct: float, entry: float, sl: float
    ) -> float:
        info = self.symbol_info(symbol)
        dist = self.stop_distance(entry, sl)
        if dist <= 0:
            raise ValueError("stop distance must be positive")
        lots = self.risk_amount(equity, risk_pct) / (dist * info.contract_size)
        return self._clamp_lots(lots)

    def risk_pct(
        self, *, symbol: str, equity: float, entry: float, sl: float, volume: float
    ) -> float:
        if equity <= 0:
            return 0.0
        loss = self.loss_per_lot(symbol, entry, sl) * volume
        return round(loss / equity * 100, 2)

    def assess(
        self,
        *,
        symbol: str,
        equity: float,
        risk_pct: float,
        entry: float,
        sl: float | None = None,
        tp: float | None = None,
        leverage: float = 100.0,
    ) -> dict:
        """Size a position from account equity and risk %, returning risk metrics."""
        info = self.symbol_info(symbol)
        entry = round(entry, info.digits)
        if sl is None:
            lots = self._clamp_lots(0.0)
            actual_risk = 0.0
            risk_amount = 0.0
        else:
            risk_amount = self.risk_amount(equity, risk_pct)
            dist = self.stop_distance(entry, sl)
            if dist <= 0:
                raise ValueError("stop distance must be positive")
            lots = self._clamp_lots(risk_amount / (dist * info.contract_size))
            actual_risk = self.risk_pct(
                symbol=symbol, equity=equity, entry=entry, sl=sl, volume=lots
            )
        reward = round(abs(tp - entry), info.digits) if tp is not None else 0.0
        ratio = self.rr(entry, sl, tp) if sl is not None and tp is not None else 0.0
        return {
            "symbol": symbol,
            "lots": lots,
            "risk_amount": risk_amount,
            "risk_pct": actual_risk,
            "reward": reward,
            "rr": ratio,
            "margin_required": self.margin_required(entry, info.contract_size, lots, leverage),
            "exposure": self.exposure_value(entry, info.contract_size, lots),
            "min_lots": self.limits.min_lots,
            "max_lots": self.limits.max_lots_per_order,
        }

    # -- limits --------------------------------------------------------------

    def validate_order(
        self,
        *,
        symbol: str,
        side: str,
        volume: float,
        entry: float,
        sl: float | None,
        equity: float,
        free_margin: float,
        open_positions_count: int,
        open_volume_symbol: float,
        leverage: float = 100.0,
    ) -> list[str]:
        """Return a list of limit violations (empty when the order is allowed)."""
        errors: list[str] = []
        if volume > self.limits.max_lots_per_order:
            errors.append(
                f"volume {volume} exceeds max lots per order ({self.limits.max_lots_per_order})"
            )
        if open_volume_symbol + volume > self.limits.max_lots_per_symbol:
            errors.append(
                f"total volume {open_volume_symbol + volume:.2f} exceeds max lots per symbol ({self.limits.max_lots_per_symbol})"
            )
        if open_positions_count >= self.limits.max_open_positions:
            errors.append(f"max open positions ({self.limits.max_open_positions}) reached")
        if sl is not None:
            pct = self.risk_pct(symbol=symbol, equity=equity, entry=entry, sl=sl, volume=volume)
            if pct > self.limits.max_risk_pct_per_trade:
                errors.append(
                    f"risk {pct:.2f}% exceeds max risk per trade ({self.limits.max_risk_pct_per_trade}%)"
                )
        margin = self.margin_required(
            entry, self.symbol_info(symbol).contract_size, volume, leverage
        )
        if margin > free_margin:
            errors.append("insufficient free margin for this order")
        return errors

    def _clamp_lots(self, lots: float) -> float:
        return round(max(self.limits.min_lots, min(lots, self.limits.max_lots_per_order)), 2)
