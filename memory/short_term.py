"""
memory/short_term.py
--------------------
In-session conversation memory for JOSEPH.

Short-term memory holds the current conversation history.
It's a sliding window — when it exceeds the limit, oldest messages
are dropped (or summarized before dropping, in Phase 4).

This is what gets sent to the LLM as conversation context.
It lives only in RAM — it's cleared when the session ends.
"""

import logging
from collections import deque
from datetime import datetime
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class Message:
    """
    Represents a single message in the conversation.

    Attributes:
        role: "user" or "assistant"
        content: The message text
        timestamp: When the message was created
    """

    def __init__(self, role: str, content: str):
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid role: {role}. Must be user/assistant/system.")
        self.role = role
        self.content = content
        self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        """Convert to the format expected by the Ollama API."""
        return {"role": self.role, "content": self.content}

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Message(role={self.role}, content='{preview}')"


class ShortTermMemory:
    """
    Manages the current conversation window.

    Keeps the last N messages (configurable via SHORT_TERM_LIMIT).
    Provides the message list in the format the LLM expects.

    Usage:
        stm = ShortTermMemory()
        stm.add("user", "Hello Joseph")
        stm.add("assistant", "Hello! How can I help?")
        messages = stm.get_messages()  # Pass to LLM
    """

    def __init__(self, limit: Optional[int] = None):
        self.limit = limit or settings.SHORT_TERM_LIMIT
        self._messages: deque[Message] = deque(maxlen=self.limit)
        self._total_added = 0  # Track total messages ever added this session
        logger.debug(f"ShortTermMemory initialized with limit={self.limit}")

    def add(self, role: str, content: str) -> Message:
        """
        Add a message to short-term memory.

        Args:
            role: "user" or "assistant"
            content: The message text

        Returns:
            The created Message object.
        """
        msg = Message(role=role, content=content)
        self._messages.append(msg)
        self._total_added += 1
        logger.debug(f"STM add [{role}]: {content[:60]}...")
        return msg

    def get_messages(self) -> list[dict]:
        """
        Return all messages as a list of dicts for the LLM API.

        Returns:
            List of {"role": ..., "content": ...} dicts.
        """
        return [msg.to_dict() for msg in self._messages]

    def get_raw_messages(self) -> list[Message]:
        """Return the raw Message objects (for summarization, etc.)."""
        return list(self._messages)

    def get_conversation_text(self) -> str:
        """
        Return the conversation as a readable text block.
        Used for summarization prompts.
        """
        lines = []
        for msg in self._messages:
            speaker = settings.USER_NAME if msg.role == "user" else settings.JOSEPH_NAME
            lines.append(f"{speaker}: {msg.content}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all messages from short-term memory."""
        count = len(self._messages)
        self._messages.clear()
        logger.info(f"Short-term memory cleared ({count} messages removed)")

    def is_near_limit(self, threshold: float = 0.8) -> bool:
        """
        Check if memory is approaching its limit.
        Used to trigger summarization before overflow.

        Args:
            threshold: Fraction of limit to consider "near" (default 80%)

        Returns:
            True if message count >= threshold * limit
        """
        return len(self._messages) >= int(self.limit * threshold)

    def should_summarize(self) -> bool:
        """
        Check if it's time to summarize and compress memory.
        Triggers every SUMMARIZE_AFTER_TURNS turns.
        """
        return (
            self._total_added > 0
            and self._total_added % settings.SUMMARIZE_AFTER_TURNS == 0
        )

    @property
    def message_count(self) -> int:
        """Current number of messages in memory."""
        return len(self._messages)

    @property
    def total_added(self) -> int:
        """Total messages added this session (including dropped ones)."""
        return self._total_added

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return (
            f"ShortTermMemory(count={len(self._messages)}, "
            f"limit={self.limit}, "
            f"total_added={self._total_added})"
        )
