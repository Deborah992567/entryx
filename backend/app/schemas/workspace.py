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


class DrawingIn(BaseModel):
    kind: str = Field(min_length=1, max_length=32)
    points_json: dict
    style_json: dict = Field(default_factory=dict)


class DrawingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    layout_id: int | None
    symbol: str
    timeframe: str
    kind: str
    points_json: dict
    style_json: dict
    created_at: datetime
    updated_at: datetime


class DrawingsSync(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(min_length=1, max_length=8)
    drawings: list[DrawingIn]
