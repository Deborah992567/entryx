"""Tests for AI provider abstraction and service (Phase 7)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.providers.ai.base import AIMessage, AIModelInfo, AIResponse
from app.providers.ai.ollama import OllamaProvider, _detect_family, _extract_size

# ------------------------------------------------------------------ base model


class TestAIMessage:
    def test_creation(self):
        msg = AIMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_frozen(self):
        msg = AIMessage(role="assistant", content="hi")
        with pytest.raises(AttributeError):
            msg.content = "changed"  # type: ignore[misc]


class TestAIResponse:
    def test_defaults(self):
        resp = AIResponse(content="ok", model="test")
        assert resp.tokens_in == 0
        assert resp.tokens_out == 0
        assert resp.grounded is True


class TestAIModelInfo:
    def test_creation(self):
        info = AIModelInfo(name="qwen2.5:1.5b", family="qwen", size="1.5b")
        assert info.family == "qwen"
        assert info.size == "1.5b"


# --------------------------------------------------------------- ollama helpers


class TestOllamaHelpers:
    def test_detect_family_llama(self):
        assert _detect_family("llama3.2:3b") == "llama"

    def test_detect_family_qwen(self):
        assert _detect_family("qwen2.5:1.5b") == "qwen"

    def test_detect_family_mistral(self):
        assert _detect_family("mistral:7b") == "mistral"

    def test_detect_family_mixtral(self):
        assert _detect_family("mixtral:8x7b") == "mistral"

    def test_detect_family_phi(self):
        assert _detect_family("phi3:mini") == "phi"

    def test_detect_family_gemma(self):
        assert _detect_family("gemma2:9b") == "gemma"

    def test_detect_family_other(self):
        assert _detect_family("custom-model") == "other"

    def test_extract_size(self):
        assert _extract_size("qwen2.5:1.5b") == "1.5b"
        assert _extract_size("llama3.2:3B") == "3b"
        assert _extract_size("mistral:7b-instruct") == "7b"

    def test_extract_size_missing(self):
        assert _extract_size("model-without-size") == ""


# --------------------------------------------------------- ollama provider


class TestOllamaProvider:
    @patch("app.providers.ai.ollama.get_settings")
    def test_init(self, mock_settings):
        mock_settings.return_value = MagicMock(
            ai_ollama_url="http://localhost:11434",
            ai_default_model="qwen2.5:1.5b",
        )
        provider = OllamaProvider()
        assert provider._default_model == "qwen2.5:1.5b"
        assert provider._base_url == "http://localhost:11434"

    @patch("app.providers.ai.ollama.get_settings")
    @pytest.mark.asyncio
    async def test_generate(self, mock_settings):
        mock_settings.return_value = MagicMock(
            ai_ollama_url="http://localhost:11434",
            ai_default_model="test-model",
        )
        provider = OllamaProvider()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": "hello from test"},
            "prompt_eval_count": 10,
            "eval_count": 5,
        }
        mock_resp.raise_for_status = MagicMock()
        provider._client = AsyncMock()
        provider._client.post = AsyncMock(return_value=mock_resp)

        messages = [AIMessage(role="user", content="hi")]
        result = await provider.generate(messages)
        assert result.content == "hello from test"
        assert result.tokens_in == 10
        assert result.tokens_out == 5
        assert result.grounded is True

    @patch("app.providers.ai.ollama.get_settings")
    @pytest.mark.asyncio
    async def test_health_check_ok(self, mock_settings):
        mock_settings.return_value = MagicMock(
            ai_ollama_url="http://localhost:11434",
            ai_default_model="test",
        )
        provider = OllamaProvider()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": [{"name": "qwen2.5:1.5b"}]}
        mock_resp.raise_for_status = MagicMock()
        provider._client = AsyncMock()
        provider._client.get = AsyncMock(return_value=mock_resp)

        result = await provider.health_check()
        assert result["status"] == "ok"
        assert result["models_loaded"] == 1

    @patch("app.providers.ai.ollama.get_settings")
    @pytest.mark.asyncio
    async def test_health_check_error(self, mock_settings):
        mock_settings.return_value = MagicMock(
            ai_ollama_url="http://localhost:11434",
            ai_default_model="test",
        )
        provider = OllamaProvider()
        provider._client = AsyncMock()
        provider._client.get = AsyncMock(side_effect=ConnectionError("refused"))

        result = await provider.health_check()
        assert result["status"] == "error"
        assert "refused" in result["error"]

    @patch("app.providers.ai.ollama.get_settings")
    @pytest.mark.asyncio
    async def test_list_models(self, mock_settings):
        mock_settings.return_value = MagicMock(
            ai_ollama_url="http://localhost:11434",
            ai_default_model="test",
        )
        provider = OllamaProvider()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen2.5:1.5b"},
                {"name": "llama3.2:3b"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        provider._client = AsyncMock()
        provider._client.get = AsyncMock(return_value=mock_resp)

        models = await provider.list_models()
        assert len(models) == 2
        assert models[0].family == "qwen"
        assert models[1].family == "llama"


# -------------------------------------------------------- market context builder


class TestMarketContextBuilder:
    def test_build_market_context_returns_string(self):
        from app.services.ai_service import AIService

        mock_db = MagicMock()
        svc = AIService(mock_db)
        result = svc.build_market_context("XAUUSD", "H1", limit=50)
        assert isinstance(result, str)
        assert "XAUUSD" in result

    def test_build_market_context_empty_data(self):
        from app.services.ai_service import AIService

        mock_db = MagicMock()
        svc = AIService(mock_db)
        with patch("app.services.ai_service.market_data") as mock_md:
            mock_md.candles.return_value = []
            result = svc.build_market_context("XAUUSD", "H1")
            assert "No candle data" in result
