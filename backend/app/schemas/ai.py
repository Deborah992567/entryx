"""AI request/response schemas (Phase 7)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    symbol: str = "XAUUSD"
    timeframe: str = "H1"


class ChatResponse(BaseModel):
    content: str
    model: str
    conversation_id: int


class AnalysisRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "H1"
    kind: str = Field(default="overview", pattern=r"^(overview|risk|structure|smc)$")


class AnalysisResponse(BaseModel):
    content: str
    model: str
    symbol: str
    timeframe: str
    kind: str


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: str | None = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    model: str
    created_at: str | None = None


class ModelInfoOut(BaseModel):
    name: str
    family: str
    size: str
    description: str


class HealthOut(BaseModel):
    status: str
    provider: str
    url: str
    models_loaded: int = 0
    default_model: str = ""
    error: str = ""


# ----------------------------------------------------------- Phase 8 schemas


class ChartExplainRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "H1"


class ScanRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["XAUUSD", "EURUSD"])
    timeframes: list[str] = Field(default_factory=lambda: ["H1", "H4"])


class RiskRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "H1"
    entry_price: float | None = None
    direction: str = Field(default="buy", pattern=r"^(buy|sell)$")
