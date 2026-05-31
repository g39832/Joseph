"""
brain/memory_relevance.py
--------------------------
Memory Relevance Engine — Phase X.

Instead of loading large amounts of memory indiscriminately,
rank memories by:
  - Relevance to the current query
  - Recency (newer = more relevant)
  - Importance (explicitly stored or reinforced)
  - Project relation (match against active project)
  - Access frequency (frequently accessed = important)

Inject only the highest-value memories to avoid prompt bloat.
"""

import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class MemoryRelevanceEngine:
    """
    Scores and ranks memories by combined relevance.

    Integrates with existing memory systems:
      - ChromaDB (semantic search)
      - SQLite long-term memory
      - Consolidated memory store

    Usage:
        mre = MemoryRelevanceEngine()
        ranked = mre.rank_memories(
            query="python project setup",
            memories=[...],
        )
        top = mre.select_top(ranked, max_tokens=500)
    """

    def __init__(self):
        self._recency_weight = 0.25
        self._importance_weight = 0.30
        self._relevance_weight = 0.35
        self._frequency_weight = 0.10

    def rank_memories(
        self,
        query: str,
        semantic_results: Optional[list[dict]] = None,
        consolidated_memories: Optional[list[dict]] = None,
        facts: Optional[dict[str, str]] = None,
        active_project: Optional[str] = None,
    ) -> list[dict]:
        """
        Rank all available memories by composite score.

        Each input memory dict should have:
          - content: str
          - relevance: float (0-1, from ChromaDB)
          - importance: float (0-1)
          - created_at: str (ISO datetime)
          - access_count: int
          - topics: list[str]
          - project_id: str

        Returns ranked list with 'score' key added.
        """
        scored: list[dict] = []
        now = datetime.now()

        if semantic_results:
            for mem in semantic_results:
                mem["memory_source"] = "semantic"
                scored.append(self._score_single(mem, query, now, active_project))

        if consolidated_memories:
            for mem in consolidated_memories:
                mem["memory_source"] = "consolidated"
                if "relevance" not in mem:
                    mem["relevance"] = self._compute_text_relevance(
                        query, mem.get("content", "")
                    )
                scored.append(self._score_single(mem, query, now, active_project))

        if facts:
            for key, value in facts.items():
                fact_entry = {
                    "content": f"{key}: {value}",
                    "relevance": self._compute_text_relevance(query, f"{key} {value}"),
                    "importance": 0.7,
                    "memory_source": "fact",
                    "topics": [key],
                }
                scored.append(self._score_single(fact_entry, query, now, active_project))

        scored.sort(key=lambda x: -x["score"])
        return scored

    def _score_single(
        self,
        mem: dict,
        query: str,
        now: datetime,
        active_project: Optional[str],
    ) -> dict:
        """Compute composite score for a single memory."""
        score = 0.0

        relevance = mem.get("relevance", 0.5)
        score += relevance * self._relevance_weight

        importance = mem.get("importance", 0.5)
        score += importance * self._importance_weight

        created_str = mem.get("created_at") or mem.get("timestamp", "")
        if created_str:
            try:
                created = datetime.fromisoformat(created_str) if isinstance(created_str, str) else now
                days_ago = (now - created).total_seconds() / 86400
                recency_score = max(0, 1.0 - (days_ago / 30))
                score += recency_score * self._recency_weight
            except (ValueError, TypeError):
                score += 0.5 * self._recency_weight
        else:
            score += 0.5 * self._recency_weight

        access_count = mem.get("access_count", 0)
        frequency_score = min(1.0, access_count / 10)
        score += frequency_score * self._frequency_weight

        if active_project:
            topics = mem.get("topics", [])
            project_id = mem.get("project_id", "")
            if active_project in topics or active_project == project_id:
                score += 0.15

        mem["score"] = round(score, 4)
        return mem

    def select_top(
        self,
        ranked: list[dict],
        max_items: int = 5,
        min_score: float = 0.15,
        max_estimate_chars: int = 1500,
    ) -> list[dict]:
        """
        Select the top-scoring memories within constraints.

        Args:
            ranked: List from rank_memories()
            max_items: Maximum number of memories to return
            min_score: Minimum composite score threshold
            max_estimate_chars: Approximate character budget

        Returns:
            Filtered list of highest-value memories.
        """
        filtered = [m for m in ranked if m.get("score", 0) >= min_score]

        filtered.sort(key=lambda x: -x["score"])

        result = []
        char_count = 0
        for mem in filtered:
            content = mem.get("content", "")
            estimated_chars = len(content) + 60
            if char_count + estimated_chars > max_estimate_chars:
                continue
            if len(result) >= max_items:
                break
            result.append(mem)
            char_count += estimated_chars

        return result

    def format_for_prompt(self, selected: list[dict]) -> str:
        """Format selected memories into a concise prompt section."""
        if not selected:
            return ""

        lines = []
        source_order = {"fact": 0, "consolidated": 1, "semantic": 2}
        selected_sorted = sorted(
            selected,
            key=lambda m: (
                source_order.get(m.get("memory_source", ""), 99),
                -m.get("score", 0),
            ),
        )

        seen = set()
        for mem in selected_sorted:
            content = mem.get("content", "").strip()
            if not content or content in seen:
                continue
            seen.add(content)

            source = mem.get("memory_source", "")
            score = mem.get("score", 0)
            prefix = ""
            if source == "fact":
                prefix = "• "
            elif source == "consolidated":
                prefix = "• "
            elif source == "semantic":
                prefix = "• "

            lines.append(f"{prefix}{content}")

        return "\n".join(lines) if lines else ""

    def _compute_text_relevance(self, query: str, text: str) -> float:
        """Simple keyword overlap relevance score (fast, no LLM)."""
        if not query or not text:
            return 0.0

        query_words = set(re.findall(r"\w+", query.lower()))
        text_words = set(re.findall(r"\w+", text.lower()))

        if not query_words or not text_words:
            return 0.0

        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "out", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only",
            "own", "same", "so", "than", "too", "very", "just", "because",
            "about", "up", "down", "it", "its", "i", "my", "me", "we",
            "you", "he", "she", "they", "this", "that", "these", "those",
            "am", "and", "but", "or", "if", "what", "which", "who", "whom",
        }
        q_filtered = query_words - stop_words
        t_filtered = text_words - stop_words

        if not q_filtered or not t_filtered:
            return 0.0

        overlap = len(q_filtered & t_filtered)
        max_len = max(len(q_filtered), len(t_filtered))
        return round(overlap / max_len, 3)


memory_relevance = MemoryRelevanceEngine()
