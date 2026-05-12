"""
brain/multi_model.py
---------------------
Multi-model routing for JOSEPH.

Uses different LLM models for different task types:
- Fast model (qwen2.5:3b or llama3.2:3b) for simple tasks
- Smart model (llama3.1 or qwen2.5:14b) for complex reasoning
- Code model (codellama or deepseek-coder) for code tasks
- Vision model (llava) for image analysis

This makes Joseph faster for simple requests while keeping
full intelligence for complex ones.

Routing logic:
  Simple (< 10 words, factual): fast model
  Code-related: code model
  Complex reasoning/analysis: smart model
  Image/vision: vision model
  Default: smart model
"""

import logging
import re
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

# Model tiers — update these based on what you have installed
MODEL_TIERS = {
    "fast": ["llama3.2:3b", "qwen2.5:3b", "phi3:mini", "llama3.1"],
    "smart": ["llama3.1", "qwen2.5:14b", "llama3.1:70b"],
    "code": ["codellama", "deepseek-coder", "llama3.1"],
    "vision": ["llava", "bakllava"],
}

# Keywords that indicate code tasks
CODE_KEYWORDS = {
    "code", "function", "class", "debug", "error", "python", "javascript",
    "typescript", "script", "program", "algorithm", "syntax", "compile",
    "import", "variable", "loop", "array", "dict", "list", "api",
    "database", "sql", "html", "css", "git", "github",
}

# Keywords that indicate complex reasoning
COMPLEX_KEYWORDS = {
    "analyze", "explain", "compare", "evaluate", "research", "summarize",
    "write", "create", "design", "plan", "strategy", "why", "how does",
    "what is the difference", "pros and cons", "recommend",
}

# Simple request patterns (use fast model)
SIMPLE_PATTERNS = [
    r"^(what|who|when|where) (is|are|was|were) .{1,30}\?$",
    r"^(yes|no|ok|sure|thanks|bye|hello|hi)$",
    r"^(open|launch|start|close) \w+$",
    r"^(what time|what day|what date)",
    r"^(how are you|how's it going)",
]


class MultiModelRouter:
    """
    Routes requests to the most appropriate LLM model.

    Usage:
        router = MultiModelRouter(llm_interface=llm)
        response = router.chat(messages, user_input)
        # Automatically uses the right model
    """

    def __init__(self, llm_interface=None):
        self._llm = llm_interface
        self._available_models: list[str] = []
        self._active_fast: Optional[str] = None
        self._active_smart: Optional[str] = None
        self._active_code: Optional[str] = None
        self._routing_stats = {"fast": 0, "smart": 0, "code": 0, "default": 0}

        if llm_interface:
            self._discover_models()

    def attach_llm(self, llm_interface) -> None:
        """Attach LLM interface and discover available models."""
        self._llm = llm_interface
        self._discover_models()

    def _discover_models(self) -> None:
        """Find which models are available in Ollama."""
        try:
            models_response = self._llm.client.list()
            self._available_models = [
                m.model.split(":")[0].lower()
                for m in models_response.models
            ]
            logger.info(f"Available models: {self._available_models}")

            # Find best available model for each tier
            for tier, candidates in MODEL_TIERS.items():
                for candidate in candidates:
                    base = candidate.split(":")[0].lower()
                    if base in self._available_models:
                        if tier == "fast":
                            self._active_fast = candidate
                        elif tier == "smart":
                            self._active_smart = candidate
                        elif tier == "code":
                            self._active_code = candidate
                        break

            logger.info(
                f"Model routing: fast={self._active_fast}, "
                f"smart={self._active_smart}, "
                f"code={self._active_code}"
            )

        except Exception as e:
            logger.debug(f"Model discovery error: {e}")

    def classify_request(self, user_input: str) -> str:
        """
        Classify a request to determine which model tier to use.

        Args:
            user_input: The user's message.

        Returns:
            Model tier: "fast", "smart", "code", or "default"
        """
        text_lower = user_input.lower().strip()

        # Check for simple patterns first
        for pattern in SIMPLE_PATTERNS:
            if re.match(pattern, text_lower, re.IGNORECASE):
                return "fast"

        # Short simple questions
        word_count = len(text_lower.split())
        if word_count <= 6 and "?" in user_input:
            return "fast"

        # Code-related
        words = set(text_lower.split())
        if words & CODE_KEYWORDS:
            return "code"

        # Complex reasoning
        if words & COMPLEX_KEYWORDS or word_count > 30:
            return "smart"

        # Default to smart for safety
        return "default"

    def get_model_for_request(self, user_input: str) -> str:
        """
        Get the best available model for a request.

        Args:
            user_input: The user's message.

        Returns:
            Model name string to use with Ollama.
        """
        tier = self.classify_request(user_input)
        self._routing_stats[tier] = self._routing_stats.get(tier, 0) + 1

        if tier == "fast" and self._active_fast:
            model = self._active_fast
        elif tier == "code" and self._active_code:
            model = self._active_code
        elif tier == "smart" and self._active_smart:
            model = self._active_smart
        else:
            model = self._active_smart or settings.OLLAMA_MODEL

        logger.debug(f"Routing [{tier}] → {model}: {user_input[:40]}")
        return model

    def chat(
        self,
        messages: list[dict],
        user_input: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Chat using the most appropriate model.

        Args:
            messages: Conversation history.
            user_input: Current user message (used for routing).
            system_prompt: Optional system prompt.

        Returns:
            Response string.
        """
        if not self._llm:
            return ""

        model = self.get_model_for_request(user_input)

        # Temporarily override the model
        original_model = self._llm._active_model
        self._llm._active_model = model

        try:
            response = self._llm.chat(
                messages=messages,
                system_prompt=system_prompt,
            )
            return response
        finally:
            self._llm._active_model = original_model

    def chat_stream(
        self,
        messages: list[dict],
        user_input: str,
        system_prompt: Optional[str] = None,
    ):
        """
        Stream a response using the most appropriate model.

        Yields response chunks.
        """
        if not self._llm:
            return

        model = self.get_model_for_request(user_input)
        original_model = self._llm._active_model
        self._llm._active_model = model

        try:
            yield from self._llm.chat_stream(
                messages=messages,
                system_prompt=system_prompt,
            )
        finally:
            self._llm._active_model = original_model

    def get_routing_stats(self) -> dict:
        """Return routing statistics."""
        total = sum(self._routing_stats.values())
        return {
            "total_requests": total,
            "by_tier": self._routing_stats,
            "models": {
                "fast": self._active_fast,
                "smart": self._active_smart,
                "code": self._active_code,
            },
        }

    def __repr__(self) -> str:
        return (
            f"MultiModelRouter("
            f"fast={self._active_fast}, "
            f"smart={self._active_smart}, "
            f"code={self._active_code})"
        )


# Module-level singleton
multi_model_router = MultiModelRouter()
