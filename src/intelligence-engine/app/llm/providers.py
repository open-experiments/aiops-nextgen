"""LLM Provider implementations.

Spec Reference: specs/04-intelligence-engine.md Section 7

Supports:
- Local vLLM (primary, for air-gapped environments)
- OpenAI API (for development/connected environments)
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from shared.observability import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Spec Reference: specs/04-intelligence-engine.md Section 7.2
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send chat request and get response."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat response."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider.

    Used for development and connected environments.
    Also compatible with vLLM's OpenAI-compatible API.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
        timeout: int = 120,
    ):
        self.model = model
        self.timeout = timeout
        self._available = bool(api_key)

        if self._available:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )
            logger.info(
                "OpenAI provider initialized",
                model=model,
                base_url=base_url or "default",
            )
        else:
            self.client = None
            logger.warning("OpenAI provider not available - no API key")

    def is_available(self) -> bool:
        return self._available

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send chat request to OpenAI."""
        if not self._available:
            raise RuntimeError("OpenAI provider not available")

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)

        # Extract response
        choice = response.choices[0]
        message = choice.message

        result = {
            "content": message.content or "",
            "role": "assistant",
            "model": response.model,
            "tokens_used": response.usage.total_tokens if response.usage else 0,
            "finish_reason": choice.finish_reason,
        }

        # Handle tool calls
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
                for tc in message.tool_calls
            ]

        return result

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat response from OpenAI."""
        if not self._available:
            raise RuntimeError("OpenAI provider not available")

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = await self.client.chat.completions.create(**kwargs)

        tool_calls_buffer = {}
        current_content = ""

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Handle content delta
            if delta.content:
                current_content += delta.content
                yield {
                    "type": "content_delta",
                    "delta": delta.content,
                }

            # Handle tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if tc.id:
                        tool_calls_buffer[tc.index] = {
                            "id": tc.id,
                            "name": tc.function.name if tc.function else "",
                            "arguments": "",
                        }
                    if tc.function and tc.function.arguments and tc.index in tool_calls_buffer:
                        tool_calls_buffer[tc.index]["arguments"] += tc.function.arguments

            # Check for finish
            if chunk.choices[0].finish_reason:
                # Emit any buffered tool calls
                if tool_calls_buffer:
                    for tc in tool_calls_buffer.values():
                        try:
                            tc["arguments"] = json.loads(tc["arguments"])
                        except json.JSONDecodeError:
                            tc["arguments"] = {}
                        yield {
                            "type": "tool_use",
                            "tool_call": tc,
                        }

                yield {
                    "type": "message_complete",
                    "finish_reason": chunk.choices[0].finish_reason,
                    "content": current_content,
                }


class LocalVLLMProvider(LLMProvider):
    """Local vLLM provider for air-gapped environments.

    Spec Reference: specs/04-intelligence-engine.md Section 7.1

    Uses OpenAI-compatible API provided by vLLM.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080/v1",
        model: str = "meta-llama/Llama-3.2-3B-Instruct",
        timeout: int = 120,
    ):
        self.model = model
        self.timeout = timeout
        self.base_url = base_url

        # vLLM uses OpenAI-compatible API with dummy key
        self.client = AsyncOpenAI(
            api_key="EMPTY",
            base_url=base_url,
            timeout=timeout,
        )
        self._available = True

        logger.info(
            "Local vLLM provider initialized",
            model=model,
            base_url=base_url,
        )

    def is_available(self) -> bool:
        return self._available

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send chat request to vLLM."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # vLLM may not support all tool calling features
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            message = choice.message

            result = {
                "content": message.content or "",
                "role": "assistant",
                "model": response.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "finish_reason": choice.finish_reason,
            }

            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    }
                    for tc in message.tool_calls
                ]

            return result

        except Exception as e:
            logger.error("vLLM request failed", error=str(e))
            self._available = False
            raise

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat response from vLLM."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            stream = await self.client.chat.completions.create(**kwargs)
            current_content = ""

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if delta.content:
                    current_content += delta.content
                    yield {
                        "type": "content_delta",
                        "delta": delta.content,
                    }

                if chunk.choices[0].finish_reason:
                    yield {
                        "type": "message_complete",
                        "finish_reason": chunk.choices[0].finish_reason,
                        "content": current_content,
                    }

        except Exception as e:
            logger.error("vLLM streaming failed", error=str(e))
            self._available = False
            raise
