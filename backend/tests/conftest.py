"""Shared test fixtures.

Uses an in-memory SQLite database with all tables created, and swaps the
`get_db` dependency so API tests run against it. WS tests use the live app
via TestClient's websocket support.
"""

from __future__ import annotations

import app.services.trading_service as trading_service
import pytest
from app.db import models as _models  # noqa: F401  (register models on Base.metadata)
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TEST_SESSION = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset module-global state (rate limiter, WS manager) between tests."""
    import app.api.deps as deps
    import app.ws.manager as ws_manager
    from app.middleware import RateLimitMiddleware

    deps._buckets.clear()
    RateLimitMiddleware.reset()
    ws_manager.manager._connections.clear()
    ws_manager.manager._channels.clear()
    ws_manager.manager._seq.clear()
    trading_service.reset_brokers()
    from app.services.backtest import backtest_store
    from app.services.strategy import strategy_engine

    strategy_engine.clear()
    backtest_store.clear()
    yield


@pytest.fixture()
def db() -> Session:
    Base.metadata.create_all(TEST_ENGINE)
    session = TEST_SESSION()
    yield session
    session.close()
    Base.metadata.drop_all(TEST_ENGINE)


@pytest.fixture()
def client(db: Session) -> TestClient:
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def user_payload() -> dict:
    return {"email": "trader@entryx.com", "password": "sup3rSecret", "name": "Test Trader"}


@pytest.fixture()
def registered_user(client: TestClient, user_payload: dict) -> dict:
    resp = client.post("/api/v1/auth/register", json=user_payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def auth_headers(client: TestClient, registered_user: dict, user_payload: dict) -> dict:
    resp = client.post("/api/v1/auth/login", json=user_payload)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
