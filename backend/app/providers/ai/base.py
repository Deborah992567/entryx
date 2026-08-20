"""Abstract AI provider interface.

Every provider must implement generate, stream, embed, and health_check.
The pipeline never invents data — it receives structured market context
and produces grounded analysis.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class AIMessage:
    """A single message in a conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class AIResponse:
    """Structured response from an AI provider."""

    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    grounded: bool = True


@dataclass(frozen=True)
class AIModelInfo:
    """Metadata about an available model."""

    name: str
    family: str  # "llama" | "qwen" | "mistral" | "other"
    size: str = ""  # "1.5b", "7b", etc.
    description: str = ""


class AIProvider(ABC):
    """Base class for all AI providers.

    Subclasses connect to a local inference engine (Ollama, llama.cpp, etc.)
    and expose a uniform interface for the EntryX AI pipeline.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[AIMessage],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AIResponse:
        """Generate a single completion from a list of messages."""

    @abstractmethod
    async def stream(
        self,
        messages: list[AIMessage],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Yield tokens as they are generated."""

    @abstractmethod
    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        """Return an embedding vector for the given text."""

    @abstractmethod
    async def health_check(self) -> dict:
        """Return provider health status (reachable, model loaded, etc.)."""

    @abstractmethod
    async def list_models(self) -> list[AIModelInfo]:
        """List available models on this provider."""
