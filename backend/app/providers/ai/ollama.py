"""Ollama AI provider — local-first inference via Ollama REST API.

Connects to a running Ollama instance (default http://localhost:11434)
and exposes generate, stream, embed, and health_check through the
AIProvider interface. No paid APIs, no data leaves the machine.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx
from app.core.config import get_settings
from app.providers.ai.base import AIMessage, AIModelInfo, AIProvider, AIResponse


class OllamaProvider(AIProvider):
    """Ollama-backed local AI provider."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ai_ollama_url.rstrip("/")
        self._default_model = settings.ai_default_model
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=5.0),
        )

    # ------------------------------------------------------------------ generate

    async def generate(
        self,
        messages: list[AIMessage],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AIResponse:
        model = model or self._default_model
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        t0 = time.monotonic()
        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        latency = (time.monotonic() - t0) * 1000
        data = resp.json()
        message = data.get("message", {})
        return AIResponse(
            content=message.get("content", ""),
            model=model,
            tokens_in=data.get("prompt_eval_count", 0),
            tokens_out=data.get("eval_count", 0),
            latency_ms=latency,
            grounded=True,
        )

    # ------------------------------------------------------------------- stream

    async def stream(
        self,
        messages: list[AIMessage],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        model = model or self._default_model
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        async with self._client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                import json

                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token

    # -------------------------------------------------------------------- embed

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        model = model or self._default_model
        payload = {"model": model, "input": text}
        resp = await self._client.post("/api/embeddings", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("embedding", [])

    # ------------------------------------------------------------ health_check

    async def health_check(self) -> dict:
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return {
                "status": "ok",
                "provider": "ollama",
                "url": self._base_url,
                "models_loaded": len(models),
                "default_model": self._default_model,
            }
        except Exception as exc:
            return {
                "status": "error",
                "provider": "ollama",
                "url": self._base_url,
                "error": str(exc),
            }

    # ---------------------------------------------------------- list_models

    async def list_models(self) -> list[AIModelInfo]:
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            result = []
            for m in models:
                name = m.get("name", "")
                family = _detect_family(name)
                size = _extract_size(name)
                result.append(AIModelInfo(name=name, family=family, size=size, description=""))
            return result
        except Exception:
            return []


def _detect_family(name: str) -> str:
    lower = name.lower()
    if "llama" in lower:
        return "llama"
    if "qwen" in lower:
        return "qwen"
    if "mistral" in lower or "mixtral" in lower:
        return "mistral"
    if "phi" in lower:
        return "phi"
    if "gemma" in lower:
        return "gemma"
    return "other"


def _extract_size(name: str) -> str:
    import re

    match = re.search(r"(\d+\.?\d*)[bB]", name)
    return match.group(1).lower() + "b" if match else ""
