"""
memory/long_term.py
-------------------
SQLite-based long-term memory for JOSEPH.

Stores:
- Conversation summaries (compressed history)
- User facts (preferences, habits, important info)
- Named memories ("remember that my birthday is...")
- Session logs

SQLite is built into Python — no extra install needed.
Data persists between sessions in ./data/memory.db

Schema:
  conversations  — session summaries
  user_facts     — extracted facts about the user
  memories       — explicitly saved memories
  sessions       — session metadata
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class LongTermMemory:
    """
    Persistent memory storage using SQLite.

    All data survives between sessions.
    Provides simple CRUD operations for memories and facts.

    Usage:
        ltm = LongTermMemory()
        ltm.save_fact("user_name", "Grayson")
        ltm.save_memory("My dog's name is Max")
        facts = ltm.get_all_facts()
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.MEMORY_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._use_memory_store = False
        self._memory_conn = None
        self._initialize_database()
        logger.info(f"LongTermMemory initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections with auto-commit/rollback."""
        try:
            if self._use_memory_store:
                if self._memory_conn is None:
                    self._memory_conn = sqlite3.connect(":memory:")
                    self._memory_conn.row_factory = sqlite3.Row
                conn = self._memory_conn
            else:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row  # Access columns by name
                conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
        except Exception as e:
            logger.warning(f"LongTermMemory falling back to in-memory store: {e}")
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
            logger.error(f"Database error: {e}")
            raise
        finally:
            if not self._use_memory_store:
                conn.close()

    def _initialize_database(self) -> None:
        """Create all tables if they don't exist."""
        try:
            with self._get_connection() as conn:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'extracted',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    importance INTEGER DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    notes TEXT DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_user_facts_key ON user_facts(key);
                CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
                CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
            """)
        except Exception as e:
            logger.warning(f"LongTermMemory using in-memory database: {e}")
            self._use_memory_store = True
            with self._get_connection() as conn:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'extracted',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    importance INTEGER DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    notes TEXT DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_user_facts_key ON user_facts(key);
                CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
                CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
            """)
        logger.debug("Database schema initialized")

    # ------------------------------------------------------------------ #
    # Session Management
    # ------------------------------------------------------------------ #

    def start_session(self, session_id: str) -> None:
        """Record the start of a new session."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
                (session_id,),
            )
        logger.info(f"Session started: {session_id}")

    def end_session(self, session_id: str, message_count: int = 0) -> None:
        """Record the end of a session."""
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE sessions
                   SET ended_at = CURRENT_TIMESTAMP, message_count = ?
                   WHERE session_id = ?""",
                (message_count, session_id),
            )
        logger.info(f"Session ended: {session_id} ({message_count} messages)")

    # ------------------------------------------------------------------ #
    # Conversation Summaries
    # ------------------------------------------------------------------ #

    def save_conversation_summary(
        self, session_id: str, summary: str, message_count: int = 0
    ) -> None:
        """
        Save a compressed summary of a conversation.

        Args:
            session_id: Unique identifier for the session.
            summary: The summarized conversation text.
            message_count: How many messages were summarized.
        """
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO conversations (session_id, summary, message_count)
                   VALUES (?, ?, ?)""",
                (session_id, summary, message_count),
            )
        logger.debug(f"Saved conversation summary for session {session_id}")

    def get_recent_summaries(self, limit: int = 5) -> list[dict]:
        """
        Retrieve the most recent conversation summaries.

        Args:
            limit: Maximum number of summaries to return.

        Returns:
            List of summary dicts with keys: summary, created_at, message_count
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT summary, created_at, message_count
                   FROM conversations
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------ #
    # User Facts
    # ------------------------------------------------------------------ #

    def save_fact(self, key: str, value: str, source: str = "extracted") -> None:
        """
        Save or update a fact about the user.

        Facts are key-value pairs like:
          "preferred_name" -> "Grayson"
          "favorite_language" -> "Python"
          "works_at" -> "Tech Company"

        Args:
            key: Fact identifier (snake_case recommended).
            value: The fact value.
            source: Where this came from (extracted/explicit/inferred).
        """
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO user_facts (key, value, source, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(key) DO UPDATE SET
                     value = excluded.value,
                     source = excluded.source,
                     updated_at = CURRENT_TIMESTAMP""",
                (key, value, source),
            )
        logger.debug(f"Saved fact: {key} = {value}")

    def get_fact(self, key: str) -> Optional[str]:
        """
        Retrieve a specific fact by key.

        Args:
            key: The fact key to look up.

        Returns:
            The fact value, or None if not found.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM user_facts WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def get_all_facts(self) -> dict[str, str]:
        """
        Return all stored user facts as a dictionary.

        Returns:
            Dict of {key: value} for all stored facts.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT key, value FROM user_facts ORDER BY key"
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def format_facts_for_context(self) -> str:
        """
        Format all user facts as a readable string for LLM context injection.

        Returns:
            Formatted string like "- preferred_name: Grayson\n- hobby: coding"
        """
        facts = self.get_all_facts()
        if not facts:
            return "No facts stored yet."
        lines = [f"- {k}: {v}" for k, v in facts.items()]
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Named Memories
    # ------------------------------------------------------------------ #

    def save_memory(
        self,
        content: str,
        tags: Optional[list[str]] = None,
        importance: int = 5,
    ) -> int:
        """
        Save an explicit memory.

        Args:
            content: The memory text.
            tags: Optional list of tags for categorization.
            importance: 1-10 scale (10 = most important).

        Returns:
            The ID of the saved memory.
        """
        tags_json = json.dumps(tags or [])
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO memories (content, tags, importance)
                   VALUES (?, ?, ?)""",
                (content, tags_json, importance),
            )
            memory_id = cursor.lastrowid
        logger.info(f"Saved memory #{memory_id}: {content[:60]}...")
        return memory_id

    def get_recent_memories(self, limit: int = 10) -> list[dict]:
        """
        Retrieve the most recently saved memories.

        Args:
            limit: Maximum number of memories to return.

        Returns:
            List of memory dicts.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT id, content, tags, importance, created_at
                   FROM memories
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

        memories = []
        for row in rows:
            m = dict(row)
            m["tags"] = json.loads(m["tags"])
            memories.append(m)
        return memories

    def get_memory_by_id(self, memory_id: int) -> Optional[dict]:
        """Return a single memory row by id."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT id, content, tags, importance, created_at, accessed_at, access_count
                   FROM memories
                   WHERE id = ?""",
                (memory_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["tags"] = json.loads(data["tags"] or "[]")
        return data

    def update_memory(
        self,
        memory_id: int,
        content: Optional[str] = None,
        tags: Optional[list[str]] = None,
        importance: Optional[int] = None,
    ) -> bool:
        """Update one or more fields on a stored memory."""
        current = self.get_memory_by_id(memory_id)
        if not current:
            return False

        new_content = content if content is not None else current["content"]
        new_tags = tags if tags is not None else current["tags"]
        new_importance = importance if importance is not None else current["importance"]

        with self._get_connection() as conn:
            conn.execute(
                """UPDATE memories
                   SET content = ?,
                       tags = ?,
                       importance = ?,
                       accessed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (new_content, json.dumps(new_tags), int(new_importance), memory_id),
            )
        return True

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a stored memory."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0

    def _set_memory_flag(self, memory_id: int, flag: str, enabled: bool) -> bool:
        """Add or remove a tag flag on a memory."""
        memory = self.get_memory_by_id(memory_id)
        if not memory:
            return False
        tags = [t for t in memory["tags"] if t != flag]
        if enabled:
            tags.append(flag)
        return self.update_memory(memory_id, tags=tags)

    def pin_memory(self, memory_id: int, enabled: bool = True) -> bool:
        """Mark a memory as important."""
        return self._set_memory_flag(memory_id, "pinned", enabled)

    def archive_memory(self, memory_id: int, enabled: bool = True) -> bool:
        """Archive or unarchive a memory."""
        return self._set_memory_flag(memory_id, "archived", enabled)

    def search_memories(self, query: str, limit: int = 5) -> list[dict]:
        """
        Simple text search through memories.
        (ChromaDB handles semantic search — this is keyword fallback.)

        Args:
            query: Search term.
            limit: Max results.

        Returns:
            List of matching memory dicts.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT id, content, tags, importance, created_at
                   FROM memories
                   WHERE content LIKE ?
                   ORDER BY importance DESC, created_at DESC
                   LIMIT ?""",
                (f"%{query}%", limit),
            ).fetchall()

        memories = []
        for row in rows:
            m = dict(row)
            m["tags"] = json.loads(m["tags"])
            # Update access tracking
            self._update_memory_access(m["id"])
            memories.append(m)
        return memories

    def _update_memory_access(self, memory_id: int) -> None:
        """Update access timestamp and count for a memory."""
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE memories
                   SET accessed_at = CURRENT_TIMESTAMP,
                       access_count = access_count + 1
                   WHERE id = ?""",
                (memory_id,),
            )

    def get_memory_stats(self) -> dict:
        """Return statistics about stored memories."""
        with self._get_connection() as conn:
            stats = conn.execute(
                """SELECT
                     COUNT(*) as total_memories,
                     (SELECT COUNT(*) FROM user_facts) as total_facts,
                     (SELECT COUNT(*) FROM conversations) as total_summaries,
                     (SELECT COUNT(*) FROM sessions) as total_sessions
                """
            ).fetchone()
        return dict(stats)

    def __repr__(self) -> str:
        stats = self.get_memory_stats()
        return (
            f"LongTermMemory(memories={stats['total_memories']}, "
            f"facts={stats['total_facts']}, "
            f"db={self.db_path.name})"
        )
