"""Workspace layout schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LayoutCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    layout_json: dict
    is_default: bool = False


class LayoutUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    layout_json: dict | None = None
    is_default: bool | None = None


class LayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    layout_json: dict
    is_default: bool
    created_at: datetime
    updated_at: datetime
