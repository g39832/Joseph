"""
memory/memory_manager.py
------------------------
The unified memory interface for JOSEPH.

This is the ONLY memory module other parts of the system should import.
It coordinates between:
  - ShortTermMemory  (current conversation, in RAM)
  - LongTermMemory   (SQLite, persists between sessions)
  - ChromaMemoryStore (vector search, persists between sessions)

The memory manager handles:
  - Adding messages to conversation history
  - Extracting and storing facts from conversations
  - Retrieving relevant context for LLM prompts
  - Summarizing conversations before they overflow
  - Session lifecycle (start/end)
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from configs.settings import settings
from memory.chroma_store import ChromaMemoryStore
from memory.long_term import LongTermMemory
from memory.short_term import ShortTermMemory

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Unified memory coordinator for JOSEPH.

    Provides a simple interface that hides the complexity of
    managing three different memory systems simultaneously.

    Usage:
        memory = MemoryManager()
        memory.start_session()

        memory.add_user_message("My favorite color is blue")
        memory.add_assistant_message("I'll remember that.")

        context = memory.get_context_for_llm()
        messages = memory.get_conversation_history()
    """

    def __init__(self):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.chroma = ChromaMemoryStore()
        self.session_id = str(uuid.uuid4())
        self._session_active = False
        logger.info(f"MemoryManager initialized (session: {self.session_id[:8]}...)")

    def start_session(self) -> None:
        """
        Begin a new session.
        Records session start in SQLite and clears short-term memory.
        """
        self.session_id = str(uuid.uuid4())
        self.short_term.clear()
        self.long_term.start_session(self.session_id)
        self._session_active = True
        logger.info(f"Session started: {self.session_id[:8]}...")

    def end_session(self) -> None:
        """
        End the current session.
        Saves a conversation summary to long-term memory.
        """
        if not self._session_active:
            return

        message_count = self.short_term.total_added

        # Save summary if there was a real conversation
        if message_count >= 2:
            self._save_session_summary()

        self.long_term.end_session(self.session_id, message_count)
        self._session_active = False
        logger.info(
            f"Session ended: {self.session_id[:8]}... "
            f"({message_count} messages)"
        )

    # ------------------------------------------------------------------ #
    # Adding Messages
    # ------------------------------------------------------------------ #

    def add_user_message(self, content: str) -> None:
        """
        Record a user message.

        Adds to short-term memory and triggers fact extraction
        if the message might contain memorable information.

        Args:
            content: The user's message text.
        """
        self.short_term.add("user", content)
        logger.debug(f"User message added to STM: {content[:60]}")

    def add_assistant_message(self, content: str) -> None:
        """
        Record Joseph's response.

        Args:
            content: Joseph's response text.
        """
        self.short_term.add("assistant", content)
        logger.debug(f"Assistant message added to STM: {content[:60]}")

    # ------------------------------------------------------------------ #
    # Retrieving Context
    # ------------------------------------------------------------------ #

    def get_conversation_history(self) -> list[dict]:
        """
        Get the current conversation as a list of message dicts.
        This is what gets passed to the LLM.

        Returns:
            List of {"role": ..., "content": ...} dicts.
        """
        return self.short_term.get_messages()

    def get_context_for_llm(self, query: Optional[str] = None) -> str:
        """
        Build a context string to inject into the system prompt.

        Combines:
        - User facts from SQLite
        - Semantically relevant memories from ChromaDB
        - Recent conversation summaries

        Args:
            query: Optional current query to find relevant memories for.

        Returns:
            Formatted context string for the system prompt.
        """
        sections = []

        # User facts
        facts = self.long_term.format_facts_for_context()
        if facts and facts != "No facts stored yet.":
            sections.append(f"## Known Facts About {settings.USER_NAME}\n{facts}")

        # Semantic memory search
        if query and self.chroma.is_available:
            semantic_results = self.chroma.search(query, n_results=3)
            if semantic_results:
                formatted = self.chroma.format_search_results(semantic_results)
                sections.append(formatted)

        # Recent conversation summaries (last 2)
        summaries = self.long_term.get_recent_summaries(limit=2)
        if summaries:
            summary_text = "\n\n".join(
                [f"[{s['created_at']}]\n{s['summary']}" for s in summaries]
            )
            sections.append(f"## Recent Conversation History\n{summary_text}")

        return "\n\n".join(sections) if sections else ""

    # ------------------------------------------------------------------ #
    # Saving Memories
    # ------------------------------------------------------------------ #

    def save_explicit_memory(self, content: str, tags: Optional[list] = None) -> None:
        """
        Explicitly save something to memory (user said "remember that...").

        Saves to both SQLite and ChromaDB for keyword + semantic search.

        Args:
            content: What to remember.
            tags: Optional categorization tags.
        """
        # Save to SQLite
        memory_id = self.long_term.save_memory(content, tags=tags, importance=8)

        # Save to ChromaDB for semantic search
        self.chroma.add_memory(
            content=content,
            memory_id=str(memory_id),
            metadata={"type": "explicit", "tags": str(tags or [])},
        )
        logger.info(f"Explicit memory saved: {content[:60]}")

    def save_fact(self, key: str, value: str) -> None:
        """
        Save a user fact (preference, habit, personal info).

        Args:
            key: Fact identifier (e.g., "favorite_color").
            value: Fact value (e.g., "blue").
        """
        self.long_term.save_fact(key, value, source="explicit")
        logger.info(f"Fact saved: {key} = {value}")

    def extract_and_save_facts(self, message: str, llm_interface=None) -> None:
        """
        Use the LLM to extract memorable facts from a user message
        and save them automatically.

        This runs asynchronously in the background — it doesn't block
        the main conversation flow.

        Args:
            message: The user's message to analyze.
            llm_interface: The LLM interface to use for extraction.
        """
        if llm_interface is None:
            return

        try:
            from brain.prompts import get_memory_extraction_prompt

            prompt = get_memory_extraction_prompt(message)
            result = llm_interface.generate(prompt, temperature=0.1)

            if result and result.strip().upper() != "NONE":
                # Save the extracted facts as a memory
                self.chroma.add_memory(
                    content=result,
                    metadata={"type": "extracted", "source_message": message[:100]},
                )
                logger.debug(f"Extracted facts saved: {result[:100]}")

        except Exception as e:
            logger.debug(f"Fact extraction skipped: {e}")

    # ------------------------------------------------------------------ #
    # Summarization
    # ------------------------------------------------------------------ #

    def _save_session_summary(self, llm_interface=None) -> None:
        """
        Summarize the current conversation and save to long-term memory.

        Called automatically at session end or when short-term memory
        approaches its limit.

        Args:
            llm_interface: Optional LLM interface for AI summarization.
                           Falls back to simple text dump if not provided.
        """
        conversation_text = self.short_term.get_conversation_text()

        if not conversation_text.strip():
            return

        summary = conversation_text  # Default: save raw conversation

        if llm_interface:
            try:
                from brain.prompts import get_summarization_prompt

                prompt = get_summarization_prompt(conversation_text)
                summary = llm_interface.generate(prompt, temperature=0.2)
                logger.debug("Conversation summarized by LLM")
            except Exception as e:
                logger.warning(f"LLM summarization failed, saving raw: {e}")

        self.long_term.save_conversation_summary(
            session_id=self.session_id,
            summary=summary,
            message_count=self.short_term.total_added,
        )

        # Also add to ChromaDB for semantic search
        self.chroma.add_memory(
            content=summary,
            metadata={
                "type": "conversation_summary",
                "session_id": self.session_id,
            },
        )

    def maybe_summarize(self, llm_interface=None) -> bool:
        """
        Check if summarization is needed and run it if so.

        Call this periodically during long conversations.

        Returns:
            True if summarization was performed.
        """
        if self.short_term.should_summarize():
            logger.info("Triggering mid-session summarization")
            self._save_session_summary(llm_interface)
            return True
        return False

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search(self, query: str) -> dict:
        """
        Search all memory systems for relevant information.

        Args:
            query: Search query.

        Returns:
            Dict with keys: semantic_results, keyword_results, facts
        """
        return {
            "semantic_results": self.chroma.search(query, n_results=5),
            "keyword_results": self.long_term.search_memories(query, limit=5),
            "facts": self.long_term.get_all_facts(),
        }

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    def get_status(self) -> dict:
        """Return a status summary of all memory systems."""
        stats = self.long_term.get_memory_stats()
        return {
            "session_id": self.session_id[:8] + "...",
            "short_term_messages": self.short_term.message_count,
            "short_term_limit": self.short_term.limit,
            "long_term_memories": stats["total_memories"],
            "long_term_facts": stats["total_facts"],
            "conversation_summaries": stats["total_summaries"],
            "total_sessions": stats["total_sessions"],
            "semantic_search": self.chroma.is_available,
            "vector_memories": self.chroma.get_count(),
        }

    def format_status(self) -> str:
        """Return a human-readable status string."""
        s = self.get_status()
        lines = [
            f"Memory Status:",
            f"  Session: {s['session_id']}",
            f"  Conversation: {s['short_term_messages']}/{s['short_term_limit']} messages",
            f"  Long-term memories: {s['long_term_memories']}",
            f"  Known facts: {s['long_term_facts']}",
            f"  Semantic search: {'✓' if s['semantic_search'] else '✗ (ChromaDB unavailable)'}",
            f"  Vector memories: {s['vector_memories']}",
        ]
        return "\n".join(lines)

    def get_companion_context(self) -> str:
        """
        Build rich companion context for the LLM.
        Includes facts, recent memories, and relationship info.
        """
        sections = []
        facts = self.long_term.get_all_facts()
        if facts:
            lines = [f"- {k}: {v}" for k, v in facts.items()]
            sections.append("User facts:\n" + "\n".join(lines))

        recent = self.long_term.get_recent_memories(limit=5)
        if recent:
            lines = [f"- {m['content']}" for m in recent]
            sections.append("Recent memories:\n" + "\n".join(lines))

        summaries = self.long_term.get_recent_summaries(limit=1)
        if summaries:
            sections.append(f"Last conversation summary:\n{summaries[0]['summary']}")

        return "\n\n".join(sections) if sections else ""

    def __repr__(self) -> str:
        return (
            f"MemoryManager(session={self.session_id[:8]}..., "
            f"stm={self.short_term.message_count}, "
            f"chroma={'on' if self.chroma.is_available else 'off'})"
        )
