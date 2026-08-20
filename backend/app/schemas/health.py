"""Health / system status schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ComponentStatus(BaseModel):
    status: str  # ok | degraded | down
    detail: Any = None


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    uptime_seconds: float | None = None
    components: dict[str, ComponentStatus]
