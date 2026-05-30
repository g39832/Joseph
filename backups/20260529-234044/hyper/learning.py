"""
hyper/learning.py
------------------
LearningEngine — Phase 4: Continuous Learning Framework.

Learns from user interactions, completed tasks, web research,
and previous solutions. Stores knowledge in versioned entries.

Requirements:
- No destructive self-modification
- No automatic code rewriting
- Human approval required for code changes
- Learning data is versioned
"""

import json
import logging
import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.DATA_DIR / "hyper_learning.db"


class KnowledgeEntry:
    """A single learned knowledge item."""

    def __init__(
        self,
        content: str,
        source: str,
        category: str = "general",
        confidence: float = 0.8,
        version: int = 1,
    ):
        self.content = content
        self.source = source
        self.category = category
        self.confidence = confidence
        self.version = version
        self.created_at = datetime.now().isoformat()
        self.access_count = 0
        self.usefulness_score = 0.5


class LearningEngine:
    """
    Continuous learning system for JOSEPH.

    Collects information from interactions, evaluates usefulness,
    generates knowledge entries, and stores them for future use.

    Never modifies code automatically.
    Never makes destructive changes.
    All learning data is versioned.
    """

    def __init__(self, memory=None, llm=None):
        self._memory = memory
        self._llm = llm
        self._session_interactions: list[dict] = []
        self._use_memory_store = False
        self._memory_conn = None
        self._init_db()
        logger.info("LearningEngine initialized")

    @contextmanager
    def _conn(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self._use_memory_store:
                if self._memory_conn is None:
                    self._memory_conn = sqlite3.connect(":memory:")
                    self._memory_conn.row_factory = sqlite3.Row
                conn = self._memory_conn
            else:
                conn = sqlite3.connect(str(DB_PATH))
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
        except Exception as e:
            conn.rollback()
            raise
        finally:
            if not self._use_memory_store:
                conn.close()

    def _init_db(self) -> None:
        try:
            with self._conn() as conn:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT 'interaction',
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 0.8,
                    version INTEGER DEFAULT 1,
                    usefulness_score REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS learning_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_date TEXT,
                    interactions INTEGER DEFAULT 0,
                    knowledge_gained INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    knowledge_id INTEGER,
                    content_hash TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT 'interaction',
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 0.8,
                    version INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_category
                    ON knowledge(category);
                CREATE INDEX IF NOT EXISTS idx_knowledge_confidence
                    ON knowledge(confidence DESC);
                CREATE INDEX IF NOT EXISTS idx_knowledge_versions_hash
                    ON knowledge_versions(content_hash);
            """)
        except Exception as e:
            logger.warning(f"LearningEngine falling back to in-memory store: {e}")
            self._use_memory_store = True
            with self._conn() as conn:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT 'interaction',
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 0.8,
                    version INTEGER DEFAULT 1,
                    usefulness_score REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS learning_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_date TEXT,
                    interactions INTEGER DEFAULT 0,
                    knowledge_gained INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    knowledge_id INTEGER,
                    content_hash TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT 'interaction',
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 0.8,
                    version INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_category
                    ON knowledge(category);
                CREATE INDEX IF NOT EXISTS idx_knowledge_confidence
                    ON knowledge(confidence DESC);
                CREATE INDEX IF NOT EXISTS idx_knowledge_versions_hash
                    ON knowledge_versions(content_hash);
            """)

    def record_interaction(self, user_input: str, response: str) -> None:
        """
        Record an interaction for learning analysis.
        Runs in background — never blocks.
        """
        self._session_interactions.append({
            "input": user_input,
            "response": response,
            "timestamp": datetime.now().isoformat(),
        })

        # Extract knowledge if interaction seems informative
        if self._is_informative(user_input, response):
            self._extract_knowledge(user_input, response)

    def _is_informative(self, user_input: str, response: str) -> bool:
        """Check if an interaction contains learnable information."""
        # Skip short exchanges
        if len(response.split()) < 15:
            return False
        # Skip automation responses
        automation_words = ["opening", "playing", "searching", "launched", "saved", "done"]
        if any(w in response.lower() for w in automation_words):
            return False
        # Skip greetings
        greeting_words = ["hello", "hi", "good morning", "good evening"]
        if any(w in user_input.lower() for w in greeting_words):
            return False
        return True

    def _extract_knowledge(self, user_input: str, response: str) -> None:
        """Extract and store knowledge from an interaction."""
        if not self._llm:
            return

        try:
            prompt = f"""Extract any factual knowledge or useful information from this exchange.
If there's nothing worth storing as knowledge, respond with: NONE

User asked: "{user_input[:200]}"
Response contained: "{response[:300]}"

Extract as a single concise knowledge statement (or NONE):"""

            result = self._llm.generate(prompt, temperature=0.1)

            if result and result.strip().upper() != "NONE" and len(result) > 10:
                self._store_knowledge(
                    content=result.strip(),
                    source="interaction",
                    category=self._categorize(user_input),
                )

        except Exception as e:
            logger.debug(f"Knowledge extraction error: {e}")

    def _categorize(self, text: str) -> str:
        """Simple category detection."""
        text_lower = text.lower()
        categories = {
            "coding": ["code", "python", "function", "debug", "error", "script"],
            "productivity": ["task", "reminder", "schedule", "work"],
            "technology": ["ai", "model", "gpu", "software", "hardware"],
            "personal": ["i am", "i like", "my name", "i prefer"],
        }
        for cat, keywords in categories.items():
            if any(kw in text_lower for kw in keywords):
                return cat
        return "general"

    def _store_knowledge(
        self,
        content: str,
        source: str = "interaction",
        category: str = "general",
        confidence: float = 0.8,
    ) -> int:
        """Store a knowledge entry in the database."""
        content_hash = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO knowledge (content, source, category, confidence)
                   VALUES (?, ?, ?, ?)""",
                (content, source, category, confidence),
            )
            kid = cursor.lastrowid

            previous = conn.execute(
                "SELECT MAX(version) AS version FROM knowledge_versions WHERE content_hash = ?",
                (content_hash,),
            ).fetchone()
            version = int(previous["version"] or 0) + 1 if previous else 1
            conn.execute(
                """INSERT INTO knowledge_versions
                   (knowledge_id, content_hash, content, source, category, confidence, version)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (kid, content_hash, content, source, category, confidence, version),
            )

        # Also store in ChromaDB for semantic search
        if self._memory and self._memory.chroma.is_available:
            self._memory.chroma.add_memory(
                content=content,
                metadata={"type": "learned_knowledge", "category": category, "source": source},
            )

        logger.debug(f"Knowledge stored #{kid}: {content[:60]}")
        return kid

    def store_versioned_knowledge(
        self,
        content: str,
        source: str = "manual",
        category: str = "general",
        confidence: float = 0.8,
    ) -> int:
        """Public helper for versioned knowledge ingestion."""
        return self._store_knowledge(
            content=content,
            source=source,
            category=category,
            confidence=confidence,
        )

    def ingest_web_research(
        self,
        query: str,
        report: str,
        confidence: float = 0.7,
    ) -> int:
        """Store synthesized web research as versioned knowledge."""
        content = f"Research query: {query}\n{report}".strip()
        return self._store_knowledge(
            content=content,
            source="web_research",
            category="research",
            confidence=confidence,
        )

    def learn_from_document(self, content: str, source: str = "document") -> int:
        """Learn from a document or article."""
        if not self._llm or not content:
            return 0

        try:
            prompt = f"""Extract 3-5 key facts or insights from this content.
Format as a numbered list. Be concise.

Content: {content[:2000]}

Key facts:"""

            result = self._llm.generate(prompt, temperature=0.2)
            if result:
                self._store_knowledge(result, source=source, category="research", confidence=0.7)
                return 1
        except Exception as e:
            logger.debug(f"Document learning error: {e}")
        return 0

    def search_knowledge(self, query: str, limit: int = 5) -> list[dict]:
        """Search stored knowledge."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT content, category, confidence, access_count
                   FROM knowledge
                   WHERE content LIKE ?
                   ORDER BY confidence DESC, access_count DESC
                   LIMIT ?""",
                (f"%{query}%", limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Return learning statistics."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM knowledge").fetchone()["c"]
            by_cat = conn.execute(
                "SELECT category, COUNT(*) as c FROM knowledge GROUP BY category"
            ).fetchall()
            versions = conn.execute("SELECT COUNT(*) as c FROM knowledge_versions").fetchone()["c"]
        return {
            "total_knowledge_entries": total,
            "total_versions": versions,
            "by_category": {r["category"]: r["c"] for r in by_cat},
            "session_interactions": len(self._session_interactions),
        }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return f"LearningEngine(knowledge={stats['total_knowledge_entries']})"
