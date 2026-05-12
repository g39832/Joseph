"""
brain/conversation_search.py
-----------------------------
Search through all past conversations and memories.

Lets you find anything Joseph has ever discussed or remembered.

Search types:
- Keyword search through conversation summaries
- Semantic search through ChromaDB
- Fact search
- Date-range search
- Combined search

Usage:
    searcher = ConversationSearch(memory_manager=memory)
    results = searcher.search("Python tutorials")
    results = searcher.search_by_date("2024-01-15")
    results = searcher.search_facts("favorite")
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class ConversationSearch:
    """
    Full-text and semantic search across all of Joseph's memory.

    Usage:
        search = ConversationSearch(memory_manager=memory)
        results = search.search("machine learning")
        print(search.format_results(results))
    """

    def __init__(self, memory_manager=None):
        self.memory = memory_manager

    def search(
        self,
        query: str,
        limit: int = 10,
        include_semantic: bool = True,
    ) -> dict:
        """
        Search all memory systems for a query.

        Args:
            query: Search term or phrase.
            limit: Maximum results per category.
            include_semantic: Whether to include semantic search.

        Returns:
            Dict with results from each memory system.
        """
        if not self.memory:
            return {"error": "Memory not available"}

        results = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "conversations": [],
            "memories": [],
            "facts": [],
            "semantic": [],
        }

        # Search conversation summaries
        try:
            summaries = self.memory.long_term.get_recent_summaries(limit=50)
            query_lower = query.lower()
            for s in summaries:
                if query_lower in s.get("summary", "").lower():
                    results["conversations"].append({
                        "summary": s["summary"][:200],
                        "date": s.get("created_at", ""),
                        "messages": s.get("message_count", 0),
                    })
            results["conversations"] = results["conversations"][:limit]
        except Exception as e:
            logger.debug(f"Conversation search error: {e}")

        # Search explicit memories
        try:
            memories = self.memory.long_term.search_memories(query, limit=limit)
            results["memories"] = memories
        except Exception as e:
            logger.debug(f"Memory search error: {e}")

        # Search facts
        try:
            all_facts = self.memory.long_term.get_all_facts()
            query_lower = query.lower()
            matching_facts = {
                k: v for k, v in all_facts.items()
                if query_lower in k.lower() or query_lower in v.lower()
            }
            results["facts"] = matching_facts
        except Exception as e:
            logger.debug(f"Facts search error: {e}")

        # Semantic search
        if include_semantic and self.memory.chroma.is_available:
            try:
                semantic = self.memory.chroma.search(query, n_results=limit)
                results["semantic"] = semantic
            except Exception as e:
                logger.debug(f"Semantic search error: {e}")

        return results

    def search_by_date(
        self,
        date_str: str,
        days_range: int = 1,
    ) -> dict:
        """
        Search conversations from a specific date.

        Args:
            date_str: Date string like "2024-01-15" or "yesterday" or "last week".
            days_range: How many days around the date to include.

        Returns:
            Search results dict.
        """
        if not self.memory:
            return {"error": "Memory not available"}

        # Parse natural date strings
        target_date = self._parse_date(date_str)
        if not target_date:
            return {"error": f"Could not parse date: {date_str}"}

        results = {
            "query": f"date:{date_str}",
            "date": target_date.strftime("%Y-%m-%d"),
            "conversations": [],
        }

        try:
            summaries = self.memory.long_term.get_recent_summaries(limit=100)
            for s in summaries:
                created = s.get("created_at", "")
                if not created:
                    continue
                try:
                    created_dt = datetime.fromisoformat(created.replace(" ", "T"))
                    diff = abs((created_dt.date() - target_date.date()).days)
                    if diff <= days_range:
                        results["conversations"].append({
                            "summary": s["summary"][:300],
                            "date": created,
                            "messages": s.get("message_count", 0),
                        })
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Date search error: {e}")

        return results

    def search_facts(self, query: str) -> dict:
        """Search specifically through stored facts."""
        if not self.memory:
            return {}

        all_facts = self.memory.long_term.get_all_facts()
        query_lower = query.lower()
        return {
            k: v for k, v in all_facts.items()
            if query_lower in k.lower() or query_lower in v.lower()
        }

    def format_results(self, results: dict) -> str:
        """Format search results as readable text."""
        if "error" in results:
            return f"Search error: {results['error']}"

        lines = [f"Search results for: '{results.get('query', '')}'"]
        total = 0

        if results.get("conversations"):
            lines.append(f"\nConversations ({len(results['conversations'])}):")
            for c in results["conversations"][:3]:
                lines.append(f"  [{c.get('date', '')[:10]}] {c['summary'][:100]}...")
            total += len(results["conversations"])

        if results.get("memories"):
            lines.append(f"\nMemories ({len(results['memories'])}):")
            for m in results["memories"][:3]:
                lines.append(f"  • {m['content'][:100]}")
            total += len(results["memories"])

        if results.get("facts"):
            lines.append(f"\nFacts ({len(results['facts'])}):")
            for k, v in list(results["facts"].items())[:5]:
                lines.append(f"  {k}: {v}")
            total += len(results["facts"])

        if results.get("semantic"):
            lines.append(f"\nSemantic matches ({len(results['semantic'])}):")
            for s in results["semantic"][:3]:
                relevance = int(s.get("relevance", 0) * 100)
                lines.append(f"  [{relevance}%] {s['content'][:100]}")
            total += len(results["semantic"])

        if total == 0:
            lines.append("\nNo results found.")
        else:
            lines.append(f"\nTotal: {total} result(s)")

        return "\n".join(lines)

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse natural language date strings."""
        date_lower = date_str.lower().strip()
        now = datetime.now()

        if date_lower in ("today", "now"):
            return now
        elif date_lower == "yesterday":
            return now - timedelta(days=1)
        elif date_lower == "last week":
            return now - timedelta(weeks=1)
        elif date_lower == "last month":
            return now - timedelta(days=30)

        # Try ISO format
        formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d", "%b %d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def __repr__(self) -> str:
        return f"ConversationSearch(memory={'connected' if self.memory else 'none'})"


# Module-level singleton
conversation_search = ConversationSearch()
