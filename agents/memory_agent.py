"""
agents/memory_agent.py
-----------------------
Memory agent — automatically extracts and stores facts from conversations.

Runs in the background after each exchange to:
- Extract user preferences and facts
- Detect emotional context
- Update relationship memory
- Summarize when needed
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class MemoryAgent:
    """
    Automatically manages memory extraction and storage.

    Runs silently in the background — never blocks conversation.
    """

    # Patterns that indicate memorable information
    MEMORABLE_PATTERNS = [
        r"\bmy name is\b",
        r"\bi am\b.{0,20}\byears old\b",
        r"\bi work\b",
        r"\bi live\b",
        r"\bi love\b",
        r"\bi hate\b",
        r"\bi prefer\b",
        r"\bi like\b",
        r"\bi don.t like\b",
        r"\bmy favorite\b",
        r"\bi always\b",
        r"\bi never\b",
        r"\bremember that\b",
        r"\bdon.t forget\b",
        r"\bmy .{0,20} is\b",
    ]

    def __init__(self, memory_manager, llm=None):
        self.memory = memory_manager
        self.llm = llm
        self._exchange_count = 0

    def set_llm(self, llm) -> None:
        self.llm = llm

    def process_exchange(self, user_message: str, assistant_response: str) -> None:
        """
        Process a conversation exchange in the background.
        Extract facts, detect preferences, update memory.

        Args:
            user_message: What the user said.
            assistant_response: What Joseph responded.
        """
        self._exchange_count += 1

        # Check if message contains memorable info
        if self._is_memorable(user_message):
            self._extract_and_store(user_message)

        # Periodic summarization
        if self._exchange_count % 8 == 0 and self.llm:
            try:
                self.memory.maybe_summarize(self.llm)
            except Exception as e:
                logger.debug(f"Summarization error: {e}")

    def _is_memorable(self, text: str) -> bool:
        """Check if text likely contains memorable information."""
        text_lower = text.lower()
        return any(
            re.search(pattern, text_lower)
            for pattern in self.MEMORABLE_PATTERNS
        )

    def _extract_and_store(self, text: str) -> None:
        """Extract facts from text and store them."""
        if not self.llm:
            # Simple rule-based extraction without LLM
            self._rule_based_extract(text)
            return

        try:
            from brain.prompts import get_memory_extraction_prompt
            prompt = get_memory_extraction_prompt(text)
            result = self.llm.generate(prompt, temperature=0.1)

            if result and result.strip().upper() != "NONE":
                self.memory.chroma.add_memory(
                    content=result,
                    metadata={"type": "auto_extracted", "source": text[:100]},
                )
                logger.debug(f"Memory agent stored: {result[:80]}")
        except Exception as e:
            logger.debug(f"Memory extraction error: {e}")

    def _rule_based_extract(self, text: str) -> None:
        """Simple rule-based fact extraction without LLM."""
        text_lower = text.lower()

        # Extract name
        name_match = re.search(r"my name is (\w+)", text_lower)
        if name_match:
            self.memory.long_term.save_fact("user_name", name_match.group(1).title())

        # Extract age
        age_match = re.search(r"i am (\d+) years old", text_lower)
        if age_match:
            self.memory.long_term.save_fact("age", age_match.group(1))

        # Extract favorites
        fav_match = re.search(r"my favorite (\w+) is (.+?)[\.\,\!]", text_lower)
        if fav_match:
            self.memory.long_term.save_fact(
                f"favorite_{fav_match.group(1)}",
                fav_match.group(2).strip()
            )
