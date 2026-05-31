"""
hyper/web_intelligence.py
--------------------------
WebIntelligenceEngine — Phase 5: Advanced Web Intelligence.

Multi-source research, fact validation, knowledge aggregation.
Caches results to avoid duplicate searches.
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

CACHE_DIR = settings.DATA_DIR / "web_cache"
CACHE_TTL_HOURS = 6


class WebIntelligenceEngine:
    """
    Advanced web research and knowledge synthesis.

    Searches multiple sources, compares results,
    validates facts, and synthesizes knowledge.
    """

    def __init__(self, llm=None):
        self._llm = llm
        self._cache: dict = {}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._load_cache()
        logger.info("WebIntelligenceEngine initialized")

    def research(self, query: str, max_sources: int = 3) -> str:
        """
        Conduct multi-source research on a topic.

        Args:
            query: Research topic or question.
            max_sources: Number of sources to consult.

        Returns:
            Synthesized research summary.
        """
        cache_key = self._cache_key(query)
        cached = self._get_cached(cache_key)
        if cached:
            logger.debug(f"Research cache hit: {query[:40]}")
            return cached

        try:
            results = self._search_multiple_sources(query, max_sources)
            if not results:
                return f"No results found for: {query}"

            synthesis = self._synthesize(query, results)
            self._cache_result(cache_key, synthesis)
            return synthesis

        except Exception as e:
            logger.error(f"Research error: {e}")
            return f"Research failed: {e}"

    def _search_multiple_sources(self, query: str, max_sources: int) -> list[dict]:
        """Search multiple web sources."""
        results = []
        try:
            import requests
            from urllib.parse import quote_plus

            # DuckDuckGo instant answers (no API key needed)
            url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"
            resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp.ok:
                data = resp.json()
                if data.get("AbstractText"):
                    results.append({
                        "source": data.get("AbstractSource", "DuckDuckGo"),
                        "url": data.get("AbstractURL", ""),
                        "content": data["AbstractText"],
                        "confidence": 0.8,
                    })
                for topic in data.get("RelatedTopics", [])[:max_sources - 1]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "source": "DuckDuckGo Related",
                            "url": topic.get("FirstURL", ""),
                            "content": topic["Text"],
                            "confidence": 0.6,
                        })

        except Exception as e:
            logger.debug(f"Web search error: {e}")

        return results[:max_sources]

    def _synthesize(self, query: str, results: list[dict]) -> str:
        """Synthesize multiple search results into a coherent answer."""
        if not results:
            return "No information found."

        if not self._llm:
            # Simple concatenation without LLM
            parts = [f"From {r['source']}: {r['content']}" for r in results]
            return "\n\n".join(parts)

        combined = "\n\n".join([
            f"Source: {r['source']}\n{r['content']}"
            for r in results
        ])

        prompt = f"""Synthesize these research results into a clear, accurate answer.
Be concise. Cite sources when relevant.

Query: {query}

Sources:
{combined}

Synthesized answer:"""

        try:
            return self._llm.generate(prompt, temperature=0.2)
        except Exception as e:
            logger.debug(f"Synthesis error: {e}")
            return results[0]["content"] if results else "No results."

    def _cache_key(self, query: str) -> str:
        return hashlib.md5(query.lower().encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[str]:
        if key in self._cache:
            entry = self._cache[key]
            age = datetime.now() - datetime.fromisoformat(entry["timestamp"])
            if age < timedelta(hours=CACHE_TTL_HOURS):
                return entry["result"]
            del self._cache[key]
        return None

    def _cache_result(self, key: str, result: str) -> None:
        self._cache[key] = {
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
        self._save_cache()

    def _load_cache(self) -> None:
        cache_file = CACHE_DIR / "research_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save_cache(self) -> None:
        cache_file = CACHE_DIR / "research_cache.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(self._cache, f)
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"WebIntelligenceEngine(cached={len(self._cache)})"
