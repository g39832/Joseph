"""
brain/llm_interface.py
----------------------
The core LLM communication layer for JOSEPH.

Handles all communication with Ollama (local LLM server).
Supports:
- Streaming responses (text appears word by word)
- Non-streaming responses (full response at once)
- Automatic fallback to secondary model
- Connection health checks
- Conversation history formatting

This module is the ONLY place that talks to Ollama.
All other modules call this one.
"""

import logging
from typing import Generator, Optional

import ollama
from ollama import Client, ResponseError

from configs.settings import settings

logger = logging.getLogger(__name__)


class LLMInterface:
    """
    Manages all interactions with the local Ollama LLM.

    Usage:
        llm = LLMInterface()
        response = llm.chat(messages, stream=False)

        # Or streaming:
        for chunk in llm.chat_stream(messages):
            print(chunk, end="", flush=True)
    """

    def __init__(self):
        self.client = Client(host=settings.OLLAMA_BASE_URL)
        self.model = settings.OLLAMA_MODEL
        self.fallback_model = settings.OLLAMA_FALLBACK_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
        self._active_model: Optional[str] = None  # Set after health check

    def health_check(self) -> bool:
        """
        Verify Ollama is running and the configured model is available.

        Returns:
            True if ready, False otherwise.
        """
        try:
            models_response = self.client.list()
            available = [m.model for m in models_response.models]
            logger.debug(f"Available Ollama models: {available}")

            # Normalize model names for comparison (strip :latest suffix)
            def normalize(name: str) -> str:
                return name.split(":")[0].lower()

            available_normalized = [normalize(m) for m in available]

            if normalize(self.model) in available_normalized:
                self._active_model = self.model
                logger.info(f"LLM ready: {self.model}")
                return True

            # Try fallback
            if normalize(self.fallback_model) in available_normalized:
                logger.warning(
                    f"Primary model '{self.model}' not found. "
                    f"Falling back to '{self.fallback_model}'."
                )
                self._active_model = self.fallback_model
                return True

            logger.error(
                f"Neither '{self.model}' nor '{self.fallback_model}' found in Ollama. "
                f"Available: {available}. "
                f"Run: ollama pull {self.model}"
            )
            return False

        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            logger.error(
                "Make sure Ollama is running. Start it with: ollama serve"
            )
            return False

    def get_active_model(self) -> str:
        """Return the currently active model name."""
        if self._active_model is None:
            self.health_check()
        return self._active_model or self.model

    def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Send a conversation to the LLM and return the full response.

        Args:
            messages: List of {"role": "user"/"assistant", "content": "..."} dicts.
            system_prompt: Optional system prompt to prepend.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.

        Returns:
            The assistant's response as a string.

        Raises:
            ConnectionError: If Ollama is not reachable.
            ValueError: If the model is not available.
        """
        formatted_messages = self._format_messages(messages, system_prompt)
        model = self.get_active_model()

        options = {
            "temperature": temperature or self.temperature,
            "num_predict": max_tokens or self.max_tokens,
            "num_ctx": 4096,      # Limit context window for speed
            "repeat_penalty": 1.1,
        }

        try:
            logger.debug(f"Sending {len(formatted_messages)} messages to {model}")
            response = self.client.chat(
                model=model,
                messages=formatted_messages,
                options=options,
                stream=False,
            )
            content = response.message.content
            logger.debug(f"LLM response length: {len(content)} chars")
            return content

        except ResponseError as e:
            if "model" in str(e).lower() and "not found" in str(e).lower():
                logger.error(f"Model not found: {model}")
                raise ValueError(f"Model '{model}' not found. Run: ollama pull {model}")
            logger.error(f"Ollama ResponseError: {e}")
            raise

        except Exception as e:
            logger.error(f"LLM chat error: {e}")
            raise ConnectionError(
                f"Failed to communicate with Ollama at {settings.OLLAMA_BASE_URL}. "
                "Is Ollama running? Try: ollama serve"
            ) from e

    def chat_stream(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Stream a response from the LLM, yielding text chunks as they arrive.

        This makes responses feel more natural — text appears progressively
        rather than all at once after a delay.

        Args:
            messages: Conversation history.
            system_prompt: Optional system prompt.
            temperature: Override temperature.
            max_tokens: Override max tokens.

        Yields:
            String chunks of the response as they stream in.
        """
        formatted_messages = self._format_messages(messages, system_prompt)
        model = self.get_active_model()

        options = {
            "temperature": temperature or self.temperature,
            "num_predict": max_tokens or self.max_tokens,
            "num_ctx": 4096,
            "repeat_penalty": 1.1,
        }

        try:
            logger.debug(f"Streaming from {model}")
            stream = self.client.chat(
                model=model,
                messages=formatted_messages,
                options=options,
                stream=True,
            )
            for chunk in stream:
                if chunk.message and chunk.message.content:
                    yield chunk.message.content

        except ResponseError as e:
            logger.error(f"Ollama stream error: {e}")
            yield f"\n[Error: {str(e)}]"

        except Exception as e:
            logger.error(f"LLM stream error: {e}")
            yield "\n[Connection error. Is Ollama running?]"

    def generate(self, prompt: str, temperature: Optional[float] = None) -> str:
        """
        Simple single-prompt generation (no conversation history).
        Useful for summarization, classification, extraction tasks.

        Args:
            prompt: The full prompt text.
            temperature: Optional temperature override.

        Returns:
            Generated text string.
        """
        model = self.get_active_model()
        options = {
            "temperature": temperature or 0.3,  # Lower temp for utility tasks
            "num_predict": 512,
        }

        try:
            response = self.client.generate(
                model=model,
                prompt=prompt,
                options=options,
            )
            return response.response.strip()

        except Exception as e:
            logger.error(f"LLM generate error: {e}")
            raise

    def _format_messages(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
    ) -> list[dict]:
        """
        Format messages for the Ollama API.

        Prepends system prompt if provided.
        Ensures all messages have 'role' and 'content' keys.

        Args:
            messages: Raw message list.
            system_prompt: Optional system message to prepend.

        Returns:
            Formatted message list ready for Ollama.
        """
        formatted = []

        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})

        for msg in messages:
            if "role" not in msg or "content" not in msg:
                logger.warning(f"Skipping malformed message: {msg}")
                continue
            formatted.append({"role": msg["role"], "content": msg["content"]})

        return formatted

    def __repr__(self) -> str:
        return (
            f"LLMInterface(model={self.model}, "
            f"active={self._active_model}, "
            f"url={settings.OLLAMA_BASE_URL})"
        )


# Module-level singleton
llm = LLMInterface()
