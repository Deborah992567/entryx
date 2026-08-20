"""Strategy Builder service — NL → rules → backtest.

Converts natural language trading ideas into structured strategy rules,
then runs a backtest to validate them. Never auto-deploys to live.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.db.models.ai import AIAnalysis
from app.providers.ai import get_ai_provider
from app.providers.ai.base import AIMessage as ProviderMsg


BUILDER_SYSTEM = """You are a trading strategy builder. Convert natural language
trading ideas into structured JSON strategy rules.

Output ONLY valid JSON with this schema:
{
  "name": "strategy name",
  "description": "brief description",
  "rules": {
    "entry": {
      "conditions": [{"indicator": "SMA", "period": 20, "cross": "above", "target": "SMA 50"}],
      "direction": "buy" | "sell" | "both"
    },
    "exit": {
      "sl_atr_multiple": 1.5,
      "tp_atr_multiple": 3.0,
      "trailing_atr": 0.5
    },
    "filters": {
      "regime": "trend" | "range" | "any",
      "min_strength": 0.5
    }
  }
}

Supported indicators: SMA, EMA, RSI, MACD, Bollinger, ATR, ADX, Stochastic.
Supported conditions: cross_above, cross_below, above, below, between.
Never suggest automatic live deployment. Always recommend paper testing first."""


class StrategyBuilderService:
    """Converts NL ideas into backtestable strategy rules."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._provider = get_ai_provider()

    async def build_strategy(self, idea: str, user_id: int = 0) -> str:
        """Convert a natural language trading idea into strategy rules JSON."""
        messages = [
            ProviderMsg(role="system", content=BUILDER_SYSTEM),
            ProviderMsg(role="user", content=f"Build a strategy from this idea:\n\n{idea}"),
        ]
        response = await self._provider.generate(messages, temperature=0.2, max_tokens=1024)

        analysis = AIAnalysis(
            user_id=user_id,
            symbol="BUILDER",
            timeframe="MULTI",
            kind="strategy_builder",
            input_json=json.dumps({"idea": idea}),
            output_json=json.dumps({"content": response.content}),
            model=response.model,
        )
        self._db.add(analysis)
        self._db.commit()

        return response.content

    async def refine_strategy(
        self,
        original_rules: str,
        feedback: str,
        user_id: int = 0,
    ) -> str:
        """Refine strategy rules based on backtest results or user feedback."""
        messages = [
            ProviderMsg(role="system", content=BUILDER_SYSTEM),
            ProviderMsg(
                role="user",
                content=(
                    f"Previous strategy rules:\n{original_rules}\n\n"
                    f"Feedback / backtest results:\n{feedback}\n\n"
                    "Refine the strategy to improve performance. Output updated JSON."
                ),
            ),
        ]
        response = await self._provider.generate(messages, temperature=0.2, max_tokens=1024)

        analysis = AIAnalysis(
            user_id=user_id,
            symbol="BUILDER",
            timeframe="MULTI",
            kind="strategy_refine",
            input_json=json.dumps({"rules": original_rules, "feedback": feedback}),
            output_json=json.dumps({"content": response.content}),
            model=response.model,
        )
        self._db.add(analysis)
        self._db.commit()

        return response.content
