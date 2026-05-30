"""
brain/structured_output.py
---------------------------
Structured output / function calling for JOSEPH.

Instead of parsing LLM text with regex, this module uses
Ollama's JSON mode to get clean, reliable structured responses.

Makes automation 10x more reliable — no more regex failures.
"""

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StructuredOutput:
    """
    Gets structured JSON responses from the LLM reliably.

    Usage:
        so = StructuredOutput(llm=llm)
        result = so.extract_tool_call("open YouTube")
        # Returns: {"tool": "open_website", "url": "https://youtube.com"}
    """

    def __init__(self, llm=None):
        self._llm = llm

    def extract(
        self,
        prompt: str,
        schema: dict,
        temperature: float = 0.0,
        retries: int = 2,
    ) -> Optional[dict]:
        """
        Extract structured data from LLM using JSON mode.

        Args:
            prompt: The prompt to send.
            schema: Expected JSON schema (for validation).
            temperature: Lower = more deterministic.
            retries: How many times to retry on parse failure.

        Returns:
            Parsed dict, or None if extraction failed.
        """
        if not self._llm:
            return None

        for attempt in range(retries + 1):
            try:
                # Use Ollama's format=json option for reliable JSON output
                response = self._llm.client.generate(
                    model=self._llm.get_active_model(),
                    prompt=prompt,
                    format="json",
                    options={
                        "temperature": temperature,
                        "num_predict": 256,
                    },
                )
                raw = response.response.strip()

                # Parse JSON
                data = json.loads(raw)

                # Basic schema validation
                if self._validate(data, schema):
                    return data
                else:
                    logger.debug(f"Schema validation failed on attempt {attempt+1}: {data}")

            except json.JSONDecodeError as e:
                logger.debug(f"JSON parse failed attempt {attempt+1}: {e}")
                if attempt < retries:
                    # Add explicit instruction on retry
                    prompt = prompt + "\n\nIMPORTANT: Respond with ONLY valid JSON, nothing else."
            except Exception as e:
                logger.debug(f"Structured output error: {e}")
                break

        return None

    def _validate(self, data: dict, schema: dict) -> bool:
        """Basic schema validation — checks required keys exist."""
        required = schema.get("required", [])
        return all(k in data for k in required)

    def extract_tool_call(self, user_input: str) -> Optional[dict]:
        """
        Extract a tool call from user input using structured output.
        More reliable than regex-based parsing.
        """
        from brain.tools import TOOL_DEFINITIONS, TOOL_PROMPT

        prompt = TOOL_PROMPT.replace("{user_input}", user_input).replace(
            "{tool_definitions}", TOOL_DEFINITIONS
        )

        schema = {"required": ["tool"]}
        return self.extract(prompt, schema, temperature=0.0)

    def extract_intent(self, user_input: str) -> str:
        """
        Classify user intent as CHAT, BROWSER, DESKTOP, MEMORY, SCHEDULE, or SYSTEM.
        Uses structured output for reliability.
        """
        prompt = f"""Classify this user request into exactly one category.
Respond with JSON: {{"intent": "CATEGORY"}}

Categories: CHAT, BROWSER, DESKTOP, MEMORY, SCHEDULE, SYSTEM

User: "{user_input}"
JSON:"""

        result = self.extract(prompt, {"required": ["intent"]}, temperature=0.0)
        if result:
            return result.get("intent", "CHAT").upper()
        return "CHAT"

    def extract_reminder_details(self, text: str) -> Optional[dict]:
        """Extract reminder message and time from natural language."""
        prompt = f"""Extract reminder details from this text.
Respond with JSON: {{"message": "what to remind", "time": "when (e.g. 3pm, in 30 minutes, in 2 hours)"}}
If no time found, use null for time.

Text: "{text}"
JSON:"""

        return self.extract(
            prompt,
            {"required": ["message"]},
            temperature=0.0,
        )

    def extract_search_query(self, text: str) -> Optional[str]:
        """Extract a clean search query from natural language."""
        prompt = f"""Extract the search query from this text.
Respond with JSON: {{"query": "the search terms"}}

Text: "{text}"
JSON:"""

        result = self.extract(prompt, {"required": ["query"]}, temperature=0.0)
        return result.get("query") if result else None
