"""Tests for live trading safeguards (Phase 9)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.providers.broker.safeguards import LiveSafeguards, SafeguardConfig
from app.services.broker import OrderRequest


def _mock_broker(equity: float = 10000.0, positions: list | None = None):
    broker = MagicMock()
    broker.equity.return_value = equity
    broker.open_positions.return_value = positions or []
    return broker


def _buy_request(symbol: str = "EURUSD", volume: float = 0.1, price: float = 1.1) -> OrderRequest:
    return OrderRequest(symbol=symbol, side="buy", type="market", volume=volume, price=price)


class TestSafeguardConfig:
    def test_defaults(self):
        cfg = SafeguardConfig()
        assert cfg.live_enabled is False
        assert cfg.kill_switch is False
        assert cfg.require_confirmation is True
        assert cfg.max_position_size == 10.0

    def test_kill_switch_blocks(self):
        cfg = SafeguardConfig(kill_switch=True, live_enabled=True)
        sg = LiveSafeguards(_mock_broker(), cfg)
        result = sg.check_order(_buy_request())
        assert result.allowed is False
        assert "Kill switch" in result.reason


class TestLiveSafeguards:
    def test_live_not_enabled(self):
        sg = LiveSafeguards(_mock_broker())
        result = sg.check_order(_buy_request())
        assert result.allowed is False
        assert "not enabled" in result.reason

    def test_require_confirmation_blocks(self):
        cfg = SafeguardConfig(live_enabled=True, require_confirmation=True)
        sg = LiveSafeguards(_mock_broker(), cfg)
        result = sg.check_order(_buy_request())
        assert result.allowed is False
        assert "confirmation" in result.reason

    def test_volume_exceeds_max(self):
        cfg = SafeguardConfig(live_enabled=True, require_confirmation=False, max_position_size=1.0)
        sg = LiveSafeguards(_mock_broker(), cfg)
        result = sg.check_order(_buy_request(volume=5.0))
        assert result.allowed is False
        assert "Volume" in result.reason

    def test_blocked_symbol(self):
        cfg = SafeguardConfig(
            live_enabled=True,
            require_confirmation=False,
            blocked_symbols=["BTCUSD"],
        )
        sg = LiveSafeguards(_mock_broker(), cfg)
        result = sg.check_order(_buy_request(symbol="BTCUSD"))
        assert result.allowed is False
        assert "blocked" in result.reason

    def test_allowed_symbols_restriction(self):
        cfg = SafeguardConfig(
            live_enabled=True,
            require_confirmation=False,
            allowed_symbols=["EURUSD"],
        )
        sg = LiveSafeguards(_mock_broker(), cfg)
        result = sg.check_order(_buy_request(symbol="GBPUSD"))
        assert result.allowed is False
        assert "not in allowed" in result.reason

    def test_max_positions_reached(self):
        cfg = SafeguardConfig(live_enabled=True, require_confirmation=False, max_open_positions=1)
        broker = _mock_broker(positions=[MagicMock()])
        sg = LiveSafeguards(broker, cfg)
        result = sg.check_order(_buy_request())
        assert result.allowed is False
        assert "Max open" in result.reason

    def test_daily_loss_limit(self):
        cfg = SafeguardConfig(
            live_enabled=True,
            require_confirmation=False,
            max_daily_loss_pct=2.0,
        )
        broker = _mock_broker(equity=10000.0)
        sg = LiveSafeguards(broker, cfg)
        sg.record_pnl(-300.0)  # 3% loss
        result = sg.check_order(_buy_request())
        assert result.allowed is False
        assert "Daily loss" in result.reason

    def test_order_passes_all_checks(self):
        cfg = SafeguardConfig(live_enabled=True, require_confirmation=False)
        sg = LiveSafeguards(_mock_broker(), cfg)
        result = sg.check_order(_buy_request())
        assert result.allowed is True

    def test_place_order_success(self):
        cfg = SafeguardConfig(live_enabled=True, require_confirmation=False)
        broker = _mock_broker()
        mock_order = MagicMock()
        broker.place_order.return_value = mock_order
        sg = LiveSafeguards(broker, cfg)
        allowed, reason, order = sg.place_order(_buy_request())
        assert allowed is True
        assert order is mock_order

    def test_place_order_rejected(self):
        sg = LiveSafeguards(_mock_broker())
        allowed, reason, order = sg.place_order(_buy_request())
        assert allowed is False
        assert order is None

    def test_trade_log(self):
        cfg = SafeguardConfig(live_enabled=True, require_confirmation=False)
        broker = _mock_broker()
        broker.place_order.return_value = MagicMock()
        sg = LiveSafeguards(broker, cfg)
        sg.place_order(_buy_request())
        log = sg.get_trade_log()
        assert len(log) == 1
        assert log[0]["success"] is True

    def test_update_config(self):
        sg = LiveSafeguards(_mock_broker())
        assert sg.config.kill_switch is False
        new_cfg = SafeguardConfig(kill_switch=True)
        sg.update_config(new_cfg)
        assert sg.config.kill_switch is True
