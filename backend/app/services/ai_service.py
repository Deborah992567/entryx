"""AI service — conversation management, analysis orchestration, and the
market-grounded AI pipeline.

Every AI response is anchored in real EntryX data (candles, indicators,
SMC structures, market structure). The service never invents prices or
signals — it explains what the data shows.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.ai import AIAnalysis, AIConversation, AIMessage
from app.providers.ai import get_ai_provider
from app.providers.ai.base import AIModelInfo, AIProvider, AIMessage as ProviderMsg
from app.services.market_data import market_data
from app.services.market_structure import analyze as analyze_structure
from app.services.smc_objects import analyze_smc


SYSTEM_PROMPT = """You are EntryX AI Copilot — a trading assistant grounded in real market data.

Rules:
- You ONLY reference data provided in the context. Never fabricate prices, indicators, or signals.
- When uncertain, say so explicitly.
- Format responses with clear structure: headers, bullet points, key levels.
- Always mention the symbol and timeframe when discussing analysis.
- Risk warnings are mandatory when discussing trade ideas."""


class AIService:
    """Manages AI conversations and market-grounded analysis."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._provider: AIProvider | None = None

    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            self._provider = get_ai_provider()
        return self._provider

    # -------------------------------------------------------- conversation CRUD

    def create_conversation(self, user_id: int, title: str = "New chat") -> AIConversation:
        conv = AIConversation(user_id=user_id, title=title, context_json="{}")
        self._db.add(conv)
        self._db.commit()
        self._db.refresh(conv)
        return conv

    def list_conversations(self, user_id: int) -> list[AIConversation]:
        return (
            self._db.query(AIConversation)
            .filter(AIConversation.user_id == user_id)
            .order_by(AIConversation.id.desc())
            .all()
        )

    def get_conversation(self, conv_id: int, user_id: int) -> AIConversation | None:
        return (
            self._db.query(AIConversation)
            .filter(AIConversation.id == conv_id, AIConversation.user_id == user_id)
            .first()
        )

    def delete_conversation(self, conv_id: int, user_id: int) -> bool:
        conv = self.get_conversation(conv_id, user_id)
        if conv is None:
            return False
        self._db.query(AIMessage).filter(AIMessage.conversation_id == conv_id).delete()
        self._db.delete(conv)
        self._db.commit()
        return True

    # ----------------------------------------------------------- message history

    def get_messages(self, conv_id: int) -> list[AIMessage]:
        return (
            self._db.query(AIMessage)
            .filter(AIMessage.conversation_id == conv_id)
            .order_by(AIMessage.id)
            .all()
        )

    def add_message(self, conv_id: int, role: str, content: str, model: str = "") -> AIMessage:
        msg = AIMessage(
            conversation_id=conv_id,
            role=role,
            content=content,
            grounded_json="{}",
            model=model,
        )
        self._db.add(msg)
        self._db.commit()
        self._db.refresh(msg)
        return msg

    # --------------------------------------------------- market-grounded context

    def build_market_context(self, symbol: str, timeframe: str, limit: int = 200) -> str:
        """Build a structured context string from real market data."""
        parts = [f"## Market Context — {symbol} {timeframe}\n"]

        try:
            candles = market_data.candles(symbol, timeframe, limit)
        except Exception:
            return "Market data unavailable for context."

        if not candles:
            return "No candle data available."

        last = candles[-1]
        parts.append(f"Latest candle: O={last['o']} H={last['h']} L={last['l']} C={last['c']} V={last['v']}")

        highs = [c["h"] for c in candles[-20:]]
        lows = [c["l"] for c in candles[-20:]]
        parts.append(f"20-bar range: {min(lows):.5f} – {max(highs):.5f}")

        closes = [c["c"] for c in candles[-50:]]
        if len(closes) >= 20:
            sma20 = sum(closes[-20:]) / 20
            parts.append(f"SMA 20: {sma20:.5f}")
        if len(closes) >= 50:
            sma50 = sum(closes[-50:]) / 50
            parts.append(f"SMA 50: {sma50:.5f}")

        try:
            structure = analyze_structure(candles, timeframe)
            regime = structure.get("regime", "unknown")
            parts.append(f"Market structure: {regime}")
            if structure.get("bos"):
                last_bos = structure["bos"][-1]
                parts.append(f"Last BOS: {last_bos.get('direction', '?')} at {last_bos.get('price', '?')}")
        except Exception:
            pass

        try:
            smc = analyze_smc(candles)
            if smc.get("fvg"):
                parts.append(f"Active FVGs: {len(smc['fvg'])}")
            if smc.get("order_blocks"):
                parts.append(f"Active order blocks: {len(smc['order_blocks'])}")
            if smc.get("liquidity_pools"):
                parts.append(f"Liquidity pools: {len(smc['liquidity_pools'])}")
        except Exception:
            pass

        return "\n".join(parts)

    # -------------------------------------------------------- chat with context

    async def chat(
        self,
        user_id: int,
        conversation_id: int,
        user_message: str,
        symbol: str = "XAUUSD",
        timeframe: str = "H1",
    ) -> str:
        """Send a message and get an AI response grounded in market data."""
        conv = self.get_conversation(conversation_id, user_id)
        if conv is None:
            conv = self.create_conversation(user_id, title=user_message[:50])

        self.add_message(conversation_id, "user", user_message)

        context = self.build_market_context(symbol, timeframe)

        history = self.get_messages(conversation_id)
        provider_messages = [ProviderMsg(role="system", content=SYSTEM_PROMPT)]
        provider_messages.append(
            ProviderMsg(role="system", content=f"Current market data:\n{context}")
        )
        for msg in history[-20:]:
            provider_messages.append(ProviderMsg(role=msg.role, content=msg.content))

        response = await self.provider.generate(provider_messages)
        self.add_message(conversation_id, "assistant", response.content, model=response.model)
        return response.content

    # ----------------------------------------------------------- quick analysis

    async def analyze_symbol(
        self,
        symbol: str,
        timeframe: str = "H1",
        kind: str = "overview",
        user_id: int = 0,
    ) -> str:
        """Run a quick AI analysis of a symbol."""
        context = self.build_market_context(symbol, timeframe)

        prompts = {
            "overview": f"Provide a concise market overview for {symbol} {timeframe}. Key levels, trend, and any notable patterns.",
            "risk": f"What are the key risk levels for {symbol} {timeframe}? Identify stop-loss zones and risk/reward considerations.",
            "structure": f"Analyze the market structure for {symbol} {timeframe}. Identify BOS/CHoCH, swing points, and regime.",
            "smc": f"Analyze Smart Money Concepts for {symbol} {timeframe}. Identify FVGs, order blocks, liquidity, and sweeps.",
        }

        prompt = prompts.get(kind, prompts["overview"])
        messages = [
            ProviderMsg(role="system", content=SYSTEM_PROMPT),
            ProviderMsg(role="system", content=f"Current market data:\n{context}"),
            ProviderMsg(role="user", content=prompt),
        ]

        response = await self.provider.generate(messages)

        analysis = AIAnalysis(
            user_id=user_id,
            symbol=symbol,
            timeframe=timeframe,
            kind=kind,
            input_json=json.dumps({"symbol": symbol, "timeframe": timeframe, "kind": kind}),
            output_json=json.dumps({"content": response.content}),
            model=response.model,
        )
        self._db.add(analysis)
        self._db.commit()

        return response.content
