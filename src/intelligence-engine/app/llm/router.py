"""LLM Router for provider selection.

Spec Reference: specs/04-intelligence-engine.md Section 7

Routes requests to the appropriate LLM provider based on configuration.
Supports fallback when primary provider is unavailable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from shared.config import LLMProvider as ProviderType
from shared.config import LLMSettings
from shared.observability import get_logger

from .providers import LLMProvider, LocalVLLMProvider, OpenAIProvider

logger = get_logger(__name__)


class LLMRouter:
    """Routes LLM requests to appropriate provider.

    Spec Reference: specs/04-intelligence-engine.md Section 7.1
    """

    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.providers: dict[str, LLMProvider] = {}
        self.primary_provider: str | None = None

        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize available providers based on configuration."""
        # Initialize based on configured provider
        if self.settings.provider == ProviderType.OPENAI:
            if self.settings.openai_api_key:
                self.providers["openai"] = OpenAIProvider(
                    api_key=self.settings.openai_api_key,
                    model=self.settings.openai_model,
                    timeout=self.settings.timeout_seconds,
                )
                self.primary_provider = "openai"
                logger.info("Primary provider: OpenAI", model=self.settings.openai_model)

        elif self.settings.provider == ProviderType.LOCAL:
            self.providers["local"] = LocalVLLMProvider(
                base_url=self.settings.local_url,
                model=self.settings.local_model,
                timeout=self.settings.timeout_seconds,
            )
            self.primary_provider = "local"
            logger.info("Primary provider: Local vLLM", model=self.settings.local_model)

        # Add fallback providers
        if "openai" not in self.providers and self.settings.openai_api_key:
            self.providers["openai"] = OpenAIProvider(
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
                timeout=self.settings.timeout_seconds,
            )
            logger.info("Fallback provider available: OpenAI")

        if not self.providers:
            logger.warning("No LLM providers configured!")

    def is_available(self) -> bool:
        """Check if any provider is available."""
        return any(p.is_available() for p in self.providers.values())

    def get_provider(self, provider_name: str | None = None) -> LLMProvider:
        """Get a provider by name or the primary provider."""
        if provider_name and provider_name in self.providers:
            provider = self.providers[provider_name]
            if provider.is_available():
                return provider

        # Return primary provider
        if self.primary_provider and self.primary_provider in self.providers:
            provider = self.providers[self.primary_provider]
            if provider.is_available():
                return provider

        # Try any available provider
        for name, provider in self.providers.items():
            if provider.is_available():
                logger.info("Using fallback provider", provider=name)
                return provider

        raise RuntimeError("No LLM provider available")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        """Send chat request through router.

        Spec Reference: specs/04-intelligence-engine.md Section 7.2
        """
        llm_provider = self.get_provider(provider)

        return await llm_provider.chat(
            messages=messages,
            tools=tools,
            temperature=temperature or self.settings.temperature,
            max_tokens=max_tokens or self.settings.max_tokens,
        )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provider: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat response through router.

        Spec Reference: specs/04-intelligence-engine.md Section 7.2
        """
        llm_provider = self.get_provider(provider)

        async for chunk in llm_provider.stream(
            messages=messages,
            tools=tools,
            temperature=temperature or self.settings.temperature,
            max_tokens=max_tokens or self.settings.max_tokens,
        ):
            yield chunk
