"""Tests for application configuration validation."""

from __future__ import annotations

from unittest.mock import patch

from app.core.config import Settings, _validate_settings


def test_is_sqlite_true() -> None:
    s = Settings(database_url="sqlite:///./entryx.db")
    assert s.is_sqlite is True


def test_is_sqlite_false() -> None:
    s = Settings(database_url="mysql+pymysql://user:pass@localhost/db")
    assert s.is_sqlite is False


def test_database_connect_args_sqlite() -> None:
    s = Settings(database_url="sqlite:///./entryx.db")
    assert s.database_connect_args == {"check_same_thread": False}


def test_database_connect_args_mysql() -> None:
    s = Settings(database_url="mysql+pymysql://user:pass@localhost/db")
    assert s.database_connect_args == {}


def test_cors_origins_from_string() -> None:
    s = Settings(cors_origins='["http://localhost:5173"]')
    assert s.cors_origins == ["http://localhost:5173"]


def test_cors_origins_from_list() -> None:
    s = Settings(cors_origins=["http://localhost:3000"])
    assert s.cors_origins == ["http://localhost:3000"]


def test_validate_settings_warns_default_secret() -> None:
    s = Settings()
    with patch("logging.getLogger") as mock_get:
        mock_logger = mock_get.return_value
        _validate_settings(s)
        assert mock_logger.warning.called


def test_validate_settings_warns_empty_encryption() -> None:
    s = Settings(encryption_key="")
    with patch("logging.getLogger") as mock_get:
        mock_logger = mock_get.return_value
        _validate_settings(s)
        calls = [str(c) for c in mock_logger.warning.call_args_list]
        assert any("ENCRYPTION_KEY" in c for c in calls)


def test_validate_settings_warns_sqlite() -> None:
    s = Settings(database_url="sqlite:///./test.db")
    with patch("logging.getLogger") as mock_get:
        mock_logger = mock_get.return_value
        _validate_settings(s)
        assert mock_logger.info.called


def test_default_settings() -> None:
    s = Settings()
    assert s.app_name == "EntryX"
    assert s.access_token_expire_minutes == 15
    assert s.refresh_token_expire_days == 30
    assert s.paper_initial_balance == 100_000.0
    assert s.paper_leverage == 100.0
    assert s.auth_rate_limit_per_minute == 10
