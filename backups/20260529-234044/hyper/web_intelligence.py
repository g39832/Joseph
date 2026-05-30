"""
hyper/web_intelligence.py
------------------------
Multi-source web research, source comparison, and cached synthesis.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urljoin

import requests

from configs.settings import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.DATA_DIR / "hyper_web_cache.db"


class WebIntelligenceEngine:
    """Best-effort web research and synthesis engine."""

    def __init__(self, llm=None, cache_path: Optional[Path] = None, timeout: int = 12):
        self.llm = llm
        self.cache_path = cache_path or DB_PATH
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._use_memory_store = False
        self._memory_conn = None
        self._init_db()

    @contextmanager
    def _conn(self):
        try:
            if self._use_memory_store:
                if self._memory_conn is None:
                    self._memory_conn = sqlite3.connect(":memory:")
                    self._memory_conn.row_factory = sqlite3.Row
                conn = self._memory_conn
            else:
                conn = sqlite3.connect(str(self.cache_path))
                conn.row_factory = sqlite3.Row
        except Exception:
            self._use_memory_store = True
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:")
                self._memory_conn.row_factory = sqlite3.Row
            conn = self._memory_conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if not self._use_memory_store:
                conn.close()

    def _init_db(self) -> None:
        try:
            with self._conn() as conn:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT UNIQUE NOT NULL,
                    query TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    hit_count INTEGER DEFAULT 0
                );
            """)
        except Exception as e:
            logger.warning(f"WebIntelligenceEngine using in-memory cache: {e}")
            self._use_memory_store = True
            with self._conn() as conn:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT UNIQUE NOT NULL,
                    query TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    hit_count INTEGER DEFAULT 0
                );
            """)

    def _cache_key(self, query: str) -> str:
        return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()

    def _get_cached(self, query: str) -> Optional[dict]:
        key = self._cache_key(query)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT result_json, hit_count FROM search_cache WHERE query_hash = ?",
                (key,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE search_cache SET hit_count = hit_count + 1 WHERE query_hash = ?",
                    (key,),
                )
                return json.loads(row["result_json"])
        return None

    def _cache(self, query: str, data: dict) -> None:
        key = self._cache_key(query)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO search_cache (query_hash, query, result_json)
                   VALUES (?, ?, ?)
                   ON CONFLICT(query_hash) DO UPDATE SET
                     query = excluded.query,
                     result_json = excluded.result_json,
                     created_at = CURRENT_TIMESTAMP""",
                (key, query, json.dumps(data, ensure_ascii=False)),
            )

    def _search_sources(self, query: str, max_sources: int = 3) -> list[dict]:
        """
        Search DuckDuckGo HTML results and return a source list.
        """
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        sources = []
        try:
            resp = requests.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            hrefs = re.findall(r'nofollow" href="(.*?)"', resp.text)
            seen = set()
            for href in hrefs:
                full = href
                if full.startswith("/"):
                    full = urljoin("https://duckduckgo.com", full)
                if full in seen:
                    continue
                seen.add(full)
                if "duckduckgo.com" in full and "uddg=" in full:
                    match = re.search(r"uddg=([^&]+)", full)
                    if match:
                        from urllib.parse import unquote

                        full = unquote(match.group(1))
                sources.append({"url": full, "title": "", "snippet": ""})
                if len(sources) >= max_sources:
                    break
        except Exception as e:
            logger.debug(f"Search failed: {e}")

        return sources

    def _fetch_text(self, url: str, limit: int = 4000) -> str:
        try:
            resp = requests.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            text = re.sub(r"<script.*?</script>", " ", resp.text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:limit]
        except Exception as e:
            logger.debug(f"Fetch failed for {url}: {e}")
            return ""

    def _synthesize(self, query: str, source_docs: list[dict]) -> str:
        if self.llm and source_docs:
            joined = "\n\n".join(
                f"Source: {doc['url']}\n{doc['content'][:1500]}" for doc in source_docs
            )
            prompt = f"""Synthesize these sources into a concise, factual answer to the research question.
Identify disagreements, mention confidence, and keep citations lightweight.

Question: {query}

Sources:
{joined}

Answer:"""
            try:
                return self.llm.generate(prompt, temperature=0.2)
            except Exception as e:
                logger.debug(f"LLM synthesis failed: {e}")

        bullet_points = []
        for doc in source_docs[:5]:
            snippet = doc["content"][:220].strip()
            bullet_points.append(f"- {snippet} ({doc['url']})")
        return "\n".join(bullet_points) if bullet_points else "No web results available."

    def research(self, query: str, max_sources: int = 3) -> str:
        """Run cached multi-source research and return a synthesized report."""
        cached = self._get_cached(query)
        if cached:
            return cached.get("report", "")

        sources = self._search_sources(query, max_sources=max_sources)
        source_docs = []
        for source in sources:
            content = self._fetch_text(source["url"])
            if content:
                source_docs.append(
                    {
                        "url": source["url"],
                        "title": source.get("title", ""),
                        "content": content,
                    }
                )

        confidence = self._estimate_confidence(source_docs)
        report = self._format_report(query, source_docs, confidence)
        payload = {
            "query": query,
            "confidence": confidence,
            "sources": source_docs,
            "report": report,
            "created_at": datetime.now().isoformat(),
        }
        self._cache(query, payload)
        return report

    def _estimate_confidence(self, source_docs: list[dict]) -> float:
        if not source_docs:
            return 0.0
        diversity = min(1.0, len(source_docs) / 3.0)
        avg_length = sum(len(doc["content"]) for doc in source_docs) / len(source_docs)
        length_score = min(1.0, avg_length / 1200.0)
        return round(min(1.0, (diversity * 0.6) + (length_score * 0.4)), 3)

    def _format_report(self, query: str, source_docs: list[dict], confidence: float) -> str:
        synthesis = self._synthesize(query, source_docs)
        lines = [
            f"Research query: {query}",
            f"Confidence: {int(confidence * 100)}%",
            "",
            synthesis,
        ]

        if source_docs:
            lines.append("")
            lines.append("Sources:")
            for doc in source_docs:
                preview = doc["content"][:180].replace("\n", " ")
                lines.append(f"- {doc['url']} :: {preview}")

        return "\n".join(lines)

    def store_to_memory(self, memory_manager, query: str, report: str) -> bool:
        """Store the research output in long-term memory if available."""
        if not memory_manager:
            return False
        try:
            memory_manager.save_explicit_memory(
                f"Research on {query}:\n{report[:2500]}",
                tags=["research", "web"],
            )
            return True
        except Exception as e:
            logger.debug(f"Storing research in memory failed: {e}")
            return False

    def get_cache_size(self) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM search_cache").fetchone()
        return int(row["c"]) if row else 0

    def __repr__(self) -> str:
        return f"WebIntelligenceEngine(cache_entries={self.get_cache_size()})"
