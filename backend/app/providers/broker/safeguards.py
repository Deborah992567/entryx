"""Live trading safeguards — the safety layer between strategy and execution.

Every live order passes through these checks before reaching the broker.
Opt-in only: live trading is disabled by default and requires explicit
user confirmation at every step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services.broker import BrokerAdapter, BrokerOrder, OrderRequest


@dataclass
class SafeguardConfig:
    """Configuration for live trading safeguards."""

    live_enabled: bool = False
    require_confirmation: bool = True
    max_position_size: float = 10.0  # lots
    max_daily_loss_pct: float = 5.0  # % of equity
    max_open_positions: int = 10
    max_order_value: float = 100000.0  # notional
    allowed_symbols: list[str] = field(default_factory=list)  # empty = all
    blocked_symbols: list[str] = field(default_factory=list)
    kill_switch: bool = False
    paper_validate_first: bool = True


@dataclass
class SafeguardResult:
    """Result of a safeguard check."""

    allowed: bool
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


class LiveSafeguards:
    """Wraps a BrokerAdapter with safety checks for live trading."""

    def __init__(self, broker: BrokerAdapter, config: SafeguardConfig | None = None) -> None:
        self._broker = broker
        self._config = config or SafeguardConfig()
        self._daily_pnl: float = 0.0
        self._daily_reset: datetime = datetime.now(timezone.utc).date()
        self._trade_log: list[dict] = []

    @property
    def config(self) -> SafeguardConfig:
        return self._config

    def update_config(self, config: SafeguardConfig) -> None:
        self._config = config

    # -------------------------------------------------------------- pre-trade checks

    def check_order(self, request: OrderRequest) -> SafeguardResult:
        """Run all safeguard checks before placing an order."""
        warnings: list[str] = []

        if self._config.kill_switch:
            return SafeguardResult(allowed=False, reason="Kill switch is active")

        if not self._config.live_enabled:
            return SafeguardResult(allowed=False, reason="Live trading is not enabled")

        if self._config.require_confirmation:
            return SafeguardResult(
                allowed=False,
                reason="Order requires explicit user confirmation",
            )

        if request.volume > self._config.max_position_size:
            return SafeguardResult(
                allowed=False,
                reason=f"Volume {request.volume} exceeds max {self._config.max_position_size}",
            )

        if request.symbol in self._config.blocked_symbols:
            return SafeguardResult(
                allowed=False,
                reason=f"Symbol {request.symbol} is blocked",
            )

        if self._config.allowed_symbols and request.symbol not in self._config.allowed_symbols:
            return SafeguardResult(
                allowed=False,
                reason=f"Symbol {request.symbol} is not in allowed list",
            )

        positions = self._broker.open_positions()
        if len(positions) >= self._config.max_open_positions:
            return SafeguardResult(
                allowed=False,
                reason=f"Max open positions ({self._config.max_open_positions}) reached",
            )

        self._check_daily_loss()
        equity = self._broker.equity()
        if equity > 0:
            loss_pct = abs(self._daily_pnl) / equity * 100
            if loss_pct >= self._config.max_daily_loss_pct:
                return SafeguardResult(
                    allowed=False,
                    reason=f"Daily loss limit reached: {loss_pct:.1f}% >= {self._config.max_daily_loss_pct}%",
                )

        if request.price is not None:
            notional = request.volume * request.price * 100  # rough estimate
            if notional > self._config.max_order_value:
                warnings.append(f"High notional value: {notional:.0f}")

        return SafeguardResult(allowed=True, warnings=warnings)

    # -------------------------------------------------------------- place with safeguards

    def place_order(self, request: OrderRequest) -> tuple[bool, str, BrokerOrder | None]:
        """Attempt to place an order through safeguards. Returns (allowed, reason, order)."""
        result = self.check_order(request)
        if not result.allowed:
            return False, result.reason, None

        try:
            order = self._broker.place_order(request)
            self._log_trade("place_order", request.symbol, request.side, request.volume, True)
            return True, "Order placed", order
        except Exception as exc:
            self._log_trade("place_order", request.symbol, request.side, request.volume, False, str(exc))
            return False, str(exc), None

    # -------------------------------------------------------------- logging

    def _log_trade(
        self,
        action: str,
        symbol: str,
        side: str,
        volume: float,
        success: bool,
        error: str = "",
    ) -> None:
        self._trade_log.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "success": success,
            "error": error,
        })

    def get_trade_log(self) -> list[dict]:
        return list(self._trade_log)

    # -------------------------------------------------------------- daily loss tracking

    def _check_daily_loss(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._daily_reset:
            self._daily_pnl = 0.0
            self._daily_reset = today

    def record_pnl(self, amount: float) -> None:
        self._check_daily_loss()
        self._daily_pnl += amount
