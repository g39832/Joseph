"""
hyper/memory_manager.py
-----------------------
Optional memory wrapper with retrieval helpers and lightweight scoring.

The existing `memory.memory_manager.MemoryManager` remains the primary
memory system. This wrapper adds convenience methods for the hyper layer
without changing the old API.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from typing import Optional

from memory.memory_manager import MemoryManager as BaseMemoryManager

logger = logging.getLogger(__name__)


class MemoryManager(BaseMemoryManager):
    """
    Hyper memory wrapper around the existing memory manager.

    It keeps backward compatibility by inheriting the current implementation,
    while adding retrieval scoring, condensed context bundles, and light
    cleanup helpers.
    """

    def _tokenize(self, text: str) -> list[str]:
        tokens = []
        for raw in text.lower().split():
            token = "".join(ch for ch in raw if ch.isalnum())
            if len(token) > 2:
                tokens.append(token)
        return tokens

    def _importance_score(self, text: str, base_score: float = 0.5) -> float:
        tokens = self._tokenize(text)
        if not tokens:
            return base_score

        counts = Counter(tokens)
        diversity = len(counts) / max(1, len(tokens))
        length_bonus = min(0.25, math.log(len(tokens) + 1) / 20.0)
        return round(min(1.0, base_score + diversity * 0.25 + length_bonus), 3)

    def get_relevant_context(self, query: str, limit: int = 5) -> dict:
        """
        Return a richer retrieval bundle for the current query.
        """
        base = self.search(query)
        semantic = base.get("semantic_results") or []
        keyword = base.get("keyword_results") or []
        facts = base.get("facts") or {}

        bundle = {
            "query": query,
            "semantic": semantic[:limit],
            "keyword": keyword[:limit],
            "facts": facts,
            "importance_hint": self._importance_score(query),
        }
        return bundle

    def build_context_string(self, query: str, limit: int = 5) -> str:
        """Format retrieval results as a prompt-ready context block."""
        bundle = self.get_relevant_context(query, limit=limit)
        sections = []

        if bundle["facts"]:
            lines = [f"- {k}: {v}" for k, v in bundle["facts"].items()]
            sections.append("Known facts:\n" + "\n".join(lines))

        if bundle["keyword"]:
            lines = [f"- {m['content']}" for m in bundle["keyword"]]
            sections.append("Relevant memories:\n" + "\n".join(lines))

        if bundle["semantic"]:
            lines = [f"- {m['content']}" for m in bundle["semantic"]]
            sections.append("Semantic matches:\n" + "\n".join(lines))

        return "\n\n".join(sections)

    def cleanup_memory(self, minimum_importance: int = 3) -> int:
        """
        Best-effort cleanup for low-value memories.

        Returns the number of entries removed from the keyword memory store.
        """
        try:
            recent = self.long_term.get_recent_memories(limit=50)
            removed = 0
            for item in recent:
                if item.get("importance", 0) < minimum_importance and len(item.get("content", "")) < 40:
                    if self.chroma.delete_memory(str(item.get("id"))):
                        removed += 1
            return removed
        except Exception as e:
            logger.debug(f"Memory cleanup skipped: {e}")
            return 0

