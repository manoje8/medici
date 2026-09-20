"""
LLM provider factory.

Centralizes provider instantiation behind a single ``create()`` call so that
``api/main.py`` never has to import concrete client classes or hard-code
constructor arguments.

Usage::

    factory = LLMFactory()
    gemini = factory.create("gemini", model="gemini-3.5-flash", timeout_seconds=30)
    groq   = factory.create("groq")           # uses config defaults
"""

from __future__ import annotations

from typing import Any

from medici.common.llm.base import BaseLLM
from medici.common.utils.config import config


class LLMProvider:
    """Known provider identifiers (convenience constants, not an enum to keep
    the factory open for extension)."""

    GEMINI = "gemini"
    GROQ = "groq"
    NVIDIA = "nvidia"
    CEREBRAS = "cerebras"


_PROVIDER_DEFAULTS: dict[str, dict[str, Any]] = {
    LLMProvider.GEMINI: {
        "model": config.GEMINI_MODEL,
    },
    LLMProvider.GROQ: {
        "model": config.GROQ_MODEL,
    },
    LLMProvider.NVIDIA: {
        "model": config.NVIDIA_MODEL,
    },
    LLMProvider.CEREBRAS: {
        "model": config.CEREBRAS_MODEL,
    },
}


def _resolve_class(provider: str) -> type[BaseLLM]:
    """Import and return the concrete ``BaseLLM`` subclass for *provider*."""
    if provider == LLMProvider.GEMINI:
        from medici.common.llm.gemini import GeminiClient

        return GeminiClient

    if provider == LLMProvider.GROQ:
        from medici.common.llm.groq import GroqClient

        return GroqClient

    if provider == LLMProvider.NVIDIA:
        from medici.common.llm.nvidia import NvidiaClient

        return NvidiaClient

    if provider == LLMProvider.CEREBRAS:
        from medici.common.llm.cerebras import CerebrasAI

        return CerebrasAI

    raise ValueError(
        f"Unknown LLM provider '{provider}'. "
        f"Registered providers: {', '.join(sorted(_PROVIDER_DEFAULTS))}"
    )


class LLMFactory:
    """
    Create :class:`BaseLLM` instances by provider name.

    ``create()`` merges caller-supplied overrides on top of config-derived
    defaults, so callers only need to specify non-default values::

        factory = LLMFactory()
        client  = factory.create("gemini", timeout_seconds=30, max_retries=2)
    """

    @staticmethod
    def create(provider: str, **overrides: Any) -> BaseLLM:
        """Instantiate and return a :class:`BaseLLM` for *provider*.

        Parameters
        ----------
        provider:
            One of ``"gemini"``, ``"groq"``, ``"nvidia"``, ``"cerebras"``
            (case-insensitive).
        **overrides:
            Any keyword argument accepted by the provider's constructor.
            These take precedence over the config-derived defaults.
        """
        provider = provider.lower().strip()

        if provider not in _PROVIDER_DEFAULTS:
            raise ValueError(
                f"Unknown LLM provider '{provider}'. "
                f"Registered providers: {', '.join(sorted(_PROVIDER_DEFAULTS))}"
            )

        cls = _resolve_class(provider)
        kwargs = {**_PROVIDER_DEFAULTS[provider], **overrides}
        return cls(**kwargs)

    @staticmethod
    def available_providers() -> list[str]:
        """Return the list of registered provider names."""
        return sorted(_PROVIDER_DEFAULTS)
