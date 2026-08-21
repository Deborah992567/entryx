"""Workspace layout schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LayoutCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="Layout display name")
    layout_json: dict = Field(description="Layout configuration (panel positions, sizes, chart settings)")
    is_default: bool = Field(default=False, description="Set as default layout for this user")


class LayoutUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120, description="New layout name")
    layout_json: dict | None = Field(default=None, description="Updated layout configuration")
    is_default: bool | None = Field(default=None, description="Set as default layout")


class LayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Unique layout ID")
    name: str = Field(description="Layout display name")
    layout_json: dict = Field(description="Layout configuration")
    is_default: bool = Field(description="Whether this is the user's default layout")
    created_at: datetime = Field(description="Layout creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class DrawingIn(BaseModel):
    kind: str = Field(min_length=1, max_length=32, description="Drawing type (trendline, rectangle, fib, text, etc)")
    points_json: dict = Field(description="Drawing anchor points in chart coordinates")
    style_json: dict = Field(default_factory=dict, description="Visual style overrides (color, width, etc)")


class DrawingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Unique drawing ID")
    layout_id: int | None = Field(description="Associated layout ID (None if standalone)")
    symbol: str = Field(description="Chart symbol")
    timeframe: str = Field(description="Chart timeframe")
    kind: str = Field(description="Drawing type")
    points_json: dict = Field(description="Drawing anchor points")
    style_json: dict = Field(description="Visual style")
    created_at: datetime = Field(description="Drawing creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class DrawingsSync(BaseModel):
    symbol: str = Field(min_length=1, max_length=32, description="Chart symbol")
    timeframe: str = Field(min_length=1, max_length=8, description="Chart timeframe")
    drawings: list[DrawingIn] = Field(description="List of drawings to sync")
