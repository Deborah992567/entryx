"""AI provider abstraction layer."""

from app.core.config import get_settings
from app.providers.ai.base import AIProvider
from app.providers.ai.ollama import OllamaProvider

__all__ = ["AIProvider", "OllamaProvider", "get_ai_provider"]

_providers: dict[str, AIProvider] = {}


def get_ai_provider() -> AIProvider:
    """Return a singleton AI provider based on the configured backend."""
    settings = get_settings()
    key = settings.ai_provider
    if key not in _providers:
        if key == "ollama":
            _providers[key] = OllamaProvider()
        else:
            _providers[key] = OllamaProvider()
    return _providers[key]
