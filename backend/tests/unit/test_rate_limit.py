"""Tests for rate limit middleware."""

from __future__ import annotations

import time

from app.middleware import RateLimitMiddleware
from starlette.testclient import TestClient


def test_rate_limit_headers_present() -> None:
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    RateLimitMiddleware.reset()
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers
    RateLimitMiddleware.reset()


def test_rate_limit_429_after_abuse() -> None:
    from app.main import app

    RateLimitMiddleware.reset()
    client = TestClient(app, raise_server_exceptions=False)
    for _ in range(200):
        client.get("/api/v1/health")
    RateLimitMiddleware.reset()


def test_reset_clears_state() -> None:
    RateLimitMiddleware._requests["fake_ip"] = [time.time()] * 5
    assert len(RateLimitMiddleware._requests["fake_ip"]) == 5
    RateLimitMiddleware.reset()
    assert "fake_ip" not in RateLimitMiddleware._requests
