"""Health / system status schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ComponentStatus(BaseModel):
    status: str = Field(description="Component status: ok, degraded, or down")
    detail: Any = Field(default=None, description="Optional detail message")


class HealthOut(BaseModel):
    status: str = Field(description="Overall system status")
    app: str = Field(description="Application name")
    version: str = Field(description="Application version")
    uptime_seconds: float | None = Field(default=None, description="Seconds since application started")
    components: dict[str, ComponentStatus] = Field(description="Individual component health statuses")
