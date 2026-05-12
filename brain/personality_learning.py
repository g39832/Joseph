"""
brain/personality_learning.py
------------------------------
Long-term personality learning for JOSEPH.

Joseph tracks which response styles you prefer and adapts over time.
Stored in SQLite — improves every session.

Tracks:
- Preferred response length (short/medium/long)
- Preferred format (prose/bullets/numbered)
- Topics you engage with most
- Times of day you're most active
- Response rating (thumbs up/down from UI)
- Vocabulary level preference
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

DB_PATH = settings.DATA_DIR / "personality_learning.db"


class PersonalityLearning:
    """
    Learns and adapts Joseph's personality based on user feedback.

    Usage:
        learning = PersonalityLearning()
        learning.record_interaction(user_msg, response, rating=1)
        prefs = learning.get_preferences()
        modifier = learning.get_style_modifier()
    """

    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info("PersonalityLearning initialized")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_message TEXT,
                    response_length INTEGER,
                    response_format TEXT,
                    rating INTEGER DEFAULT 0,
                    hour_of_day INTEGER,
                    topic TEXT DEFAULT 'general',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    confidence REAL DEFAULT 0.5,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS topic_engagement (
                    topic TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 1,
                    avg_rating REAL DEFAULT 0.0,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def record_interaction(
        self,
        user_message: str,
        response: str,
        rating: int = 0,
    ) -> None:
        """
        Record an interaction for learning.

        Args:
            user_message: What the user said.
            response: Joseph's response.
            rating: User rating (-1=bad, 0=neutral, 1=good).
        """
        response_length = len(response.split())
        response_format = self._detect_format(response)
        hour = datetime.now().hour
        topic = self._detect_topic(user_message)

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO interactions
                   (user_message, response_length, response_format, rating, hour_of_day, topic)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_message[:200], response_length, response_format, rating, hour, topic),
            )

            # Update topic engagement
            conn.execute(
                """INSERT INTO topic_engagement (topic, count, avg_rating, last_seen)
                   VALUES (?, 1, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(topic) DO UPDATE SET
                     count = count + 1,
                     avg_rating = (avg_rating * count + ?) / (count + 1),
                     last_seen = CURRENT_TIMESTAMP""",
                (topic, float(rating), float(rating)),
            )

        # Update learned preferences
        self._update_preferences()

    def rate_last_response(self, rating: int) -> None:
        """
        Rate the most recent response.

        Args:
            rating: -1 (bad), 0 (neutral), 1 (good)
        """
        with self._conn() as conn:
            conn.execute(
                "UPDATE interactions SET rating=? ORDER BY id DESC LIMIT 1",
                (rating,),
            )
        self._update_preferences()
        logger.info(f"Response rated: {rating}")

    def _update_preferences(self) -> None:
        """Recalculate preferences from interaction history."""
        with self._conn() as conn:
            # Preferred response length
            row = conn.execute(
                """SELECT AVG(response_length) as avg_len,
                          AVG(CASE WHEN rating > 0 THEN response_length END) as liked_len
                   FROM interactions WHERE created_at > datetime('now', '-30 days')"""
            ).fetchone()

            if row and row["liked_len"]:
                liked_len = row["liked_len"]
                if liked_len < 50:
                    length_pref = "short"
                elif liked_len < 150:
                    length_pref = "medium"
                else:
                    length_pref = "long"
                self._set_preference("response_length", length_pref, 0.7)

            # Preferred format
            row = conn.execute(
                """SELECT response_format, COUNT(*) as cnt,
                          AVG(rating) as avg_rating
                   FROM interactions
                   WHERE rating > 0 AND created_at > datetime('now', '-30 days')
                   GROUP BY response_format
                   ORDER BY avg_rating DESC LIMIT 1"""
            ).fetchone()

            if row:
                self._set_preference("response_format", row["response_format"], 0.6)

            # Most active hours
            row = conn.execute(
                """SELECT hour_of_day, COUNT(*) as cnt
                   FROM interactions
                   WHERE created_at > datetime('now', '-7 days')
                   GROUP BY hour_of_day
                   ORDER BY cnt DESC LIMIT 1"""
            ).fetchone()

            if row:
                self._set_preference("peak_hour", str(row["hour_of_day"]), 0.8)

    def _set_preference(self, key: str, value: str, confidence: float) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO preferences (key, value, confidence, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(key) DO UPDATE SET
                     value=excluded.value,
                     confidence=excluded.confidence,
                     updated_at=CURRENT_TIMESTAMP""",
                (key, value, confidence),
            )

    def get_preferences(self) -> dict:
        """Return all learned preferences."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT key, value, confidence FROM preferences"
            ).fetchall()
        return {r["key"]: {"value": r["value"], "confidence": r["confidence"]} for r in rows}

    def get_style_modifier(self) -> str:
        """
        Generate a style modifier string for the system prompt.
        Based on learned preferences.
        """
        prefs = self.get_preferences()
        parts = []

        length = prefs.get("response_length", {}).get("value", "medium")
        if length == "short":
            parts.append("Keep responses brief and to the point.")
        elif length == "long":
            parts.append("The user appreciates detailed, thorough responses.")

        fmt = prefs.get("response_format", {}).get("value", "prose")
        if fmt == "bullets":
            parts.append("Use bullet points when listing multiple items.")
        elif fmt == "numbered":
            parts.append("Use numbered lists for sequential information.")

        return " ".join(parts)

    def get_top_topics(self, limit: int = 5) -> list[dict]:
        """Return most engaged topics."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT topic, count, avg_rating
                   FROM topic_engagement
                   ORDER BY count DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Return learning statistics."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM interactions").fetchone()["c"]
            rated = conn.execute(
                "SELECT COUNT(*) as c FROM interactions WHERE rating != 0"
            ).fetchone()["c"]
            avg_rating = conn.execute(
                "SELECT AVG(rating) as r FROM interactions WHERE rating != 0"
            ).fetchone()["r"] or 0

        return {
            "total_interactions": total,
            "rated_interactions": rated,
            "avg_rating": round(avg_rating, 2),
            "preferences": self.get_preferences(),
        }

    def _detect_format(self, text: str) -> str:
        """Detect the format of a response."""
        if text.count("\n- ") >= 2 or text.count("\n• ") >= 2:
            return "bullets"
        if text.count("\n1.") >= 2 or text.count("\n2.") >= 1:
            return "numbered"
        return "prose"

    def _detect_topic(self, text: str) -> str:
        """Detect the topic of a message."""
        text_lower = text.lower()
        topics = {
            "coding": ["code", "python", "function", "debug", "error", "script"],
            "productivity": ["task", "reminder", "schedule", "meeting", "work"],
            "information": ["what", "how", "why", "explain", "tell me"],
            "automation": ["open", "search", "play", "launch", "find"],
            "personal": ["i am", "i like", "my name", "i prefer", "i work"],
        }
        for topic, keywords in topics.items():
            if any(kw in text_lower for kw in keywords):
                return topic
        return "general"

    def __repr__(self) -> str:
        stats = self.get_stats()
        return f"PersonalityLearning(interactions={stats['total_interactions']})"


# Module-level singleton
personality_learning = PersonalityLearning()
