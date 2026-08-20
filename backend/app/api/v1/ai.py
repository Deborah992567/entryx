"""AI Copilot API routes (Phase 7).

Endpoints for chat, quick analysis, conversation management, model listing,
and provider health checks. All grounded in real EntryX market data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.ai import (
    AnalysisRequest,
    AnalysisResponse,
    ChartExplainRequest,
    ChatRequest,
    ChatResponse,
    ConversationOut,
    HealthOut,
    MessageOut,
    ModelInfoOut,
    RiskRequest,
    ScanRequest,
)
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


# --------------------------------------------------------------- chat

@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    svc = AIService(db)
    content = await svc.chat(
        user_id=user.id,
        conversation_id=0,
        user_message=body.message,
        symbol=body.symbol,
        timeframe=body.timeframe,
    )
    return ChatResponse(content=content, model="", conversation_id=0)


@router.post("/conversations", response_model=ConversationOut)
def create_conversation(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    svc = AIService(db)
    conv = svc.create_conversation(user.id)
    return ConversationOut(id=conv.id, title=conv.title)


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationOut]:
    svc = AIService(db)
    convs = svc.list_conversations(user.id)
    return [ConversationOut(id=c.id, title=c.title) for c in convs]


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def get_messages(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    svc = AIService(db)
    conv = svc.get_conversation(conv_id, user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    msgs = svc.get_messages(conv_id)
    return [MessageOut(id=m.id, role=m.role, content=m.content, model=m.model) for m in msgs]


@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    svc = AIService(db)
    if not svc.delete_conversation(conv_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


# ----------------------------------------------------------- quick analysis

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    body: AnalysisRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    svc = AIService(db)
    content = await svc.analyze_symbol(
        symbol=body.symbol,
        timeframe=body.timeframe,
        kind=body.kind,
        user_id=user.id,
    )
    return AnalysisResponse(
        content=content,
        model="",
        symbol=body.symbol,
        timeframe=body.timeframe,
        kind=body.kind,
    )


# ----------------------------------------------------------- Phase 8: AI apps


@router.post("/explain-chart", response_model=AnalysisResponse)
async def explain_chart(
    body: ChartExplainRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    svc = AIService(db)
    content = await svc.explain_chart(body.symbol, body.timeframe, user_id=user.id)
    return AnalysisResponse(
        content=content, model="", symbol=body.symbol,
        timeframe=body.timeframe, kind="chart_explainer",
    )


@router.post("/scan", response_model=AnalysisResponse)
async def scan_market(
    body: ScanRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    svc = AIService(db)
    content = await svc.scan_market(body.symbols, body.timeframes, user_id=user.id)
    return AnalysisResponse(
        content=content, model="",
        symbol=",".join(body.symbols),
        timeframe=",".join(body.timeframes),
        kind="scanner",
    )


@router.post("/risk", response_model=AnalysisResponse)
async def risk_copilot(
    body: RiskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    svc = AIService(db)
    content = await svc.explain_risk(
        symbol=body.symbol, timeframe=body.timeframe,
        entry_price=body.entry_price, direction=body.direction,
        user_id=user.id,
    )
    return AnalysisResponse(
        content=content, model="", symbol=body.symbol,
        timeframe=body.timeframe, kind="risk_copilot",
    )


# ----------------------------------------------------------- models + health

@router.get("/models", response_model=list[ModelInfoOut])
async def list_models(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ModelInfoOut]:
    svc = AIService(db)
    models = await svc.provider.list_models()
    return [ModelInfoOut(name=m.name, family=m.family, size=m.size, description=m.description) for m in models]


@router.get("/health", response_model=HealthOut)
async def health(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HealthOut:
    svc = AIService(db)
    result = await svc.provider.health_check()
    return HealthOut(**result)
