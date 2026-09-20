"""
Unit tests for LLMFactory.

Covers:
- Creating each registered provider returns the correct BaseLLM subclass
- Unknown provider raises ValueError
- Override kwargs are forwarded to the constructor
- available_providers() lists all registered providers
"""

from unittest.mock import MagicMock, patch

import pytest

from medici.common.llm.base import BaseLLM
from medici.common.llm.llm_factory import LLMFactory, LLMProvider


class TestLLMFactory:
    """Tests for the LLMFactory.create() method."""

    @patch("medici.common.llm.gemini.config")
    @patch("medici.common.llm.gemini.genai")
    def test_create_gemini_returns_gemini_client(self, mock_genai, mock_config):
        mock_config.GEMINI_API_KEY = "test-key"
        mock_genai.Client.return_value = MagicMock()

        client = LLMFactory.create("gemini", timeout_seconds=10, max_retries=1)

        from medici.common.llm.gemini import GeminiClient

        assert isinstance(client, GeminiClient)
        assert isinstance(client, BaseLLM)
        assert client.timeout_seconds == 10
        assert client.max_retries == 1

    @patch("medici.common.llm.groq.config")
    @patch("medici.common.llm.groq.ChatGroq")
    def test_create_groq_returns_groq_client(self, mock_chat_groq, mock_config):
        mock_config.GROQ_API_KEY = "test-key"
        mock_chat_groq.return_value = MagicMock()

        client = LLMFactory.create("groq", timeout_seconds=15)

        from medici.common.llm.groq import GroqClient

        assert isinstance(client, GroqClient)
        assert isinstance(client, BaseLLM)
        assert client.timeout_seconds == 15

    def test_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown LLM provider 'nonexistent'"):
            LLMFactory.create("nonexistent")

    def test_available_providers_lists_all(self):
        providers = LLMFactory.available_providers()
        assert "gemini" in providers
        assert "groq" in providers
        assert "nvidia" in providers
        assert "cerebras" in providers

    @patch("medici.common.llm.gemini.config")
    @patch("medici.common.llm.gemini.genai")
    def test_model_override_takes_precedence(self, mock_genai, mock_config):
        mock_config.GEMINI_API_KEY = "test-key"
        mock_genai.Client.return_value = MagicMock()

        client = LLMFactory.create("gemini", model="gemini-custom-model")
        assert client.model == "gemini-custom-model"

    @patch("medici.common.llm.gemini.config")
    @patch("medici.common.llm.gemini.genai")
    def test_case_insensitive_provider(self, mock_genai, mock_config):
        mock_config.GEMINI_API_KEY = "test-key"
        mock_genai.Client.return_value = MagicMock()

        client = LLMFactory.create("GEMINI")
        assert client is not None

    def test_provider_constants_match_registry(self):
        providers = LLMFactory.available_providers()
        assert LLMProvider.GEMINI in providers
        assert LLMProvider.GROQ in providers
        assert LLMProvider.NVIDIA in providers
        assert LLMProvider.CEREBRAS in providers
