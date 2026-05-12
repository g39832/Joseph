"""
brain/notes.py
---------------
Notes and task management for JOSEPH.

Stores notes and tasks in SQLite.
Supports:
- Quick notes ("add to my notes: buy groceries")
- Task list with completion tracking
- Searching notes
- Daily briefing integration

All data persists between sessions.
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class NotesManager:
    """
    Manages notes and tasks for JOSEPH.

    Usage:
        notes = NotesManager()
        notes.add_note("Buy groceries")
        notes.add_task("Finish the report")
        notes.complete_task(1)
        print(notes.get_all_notes())
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.DATA_DIR / "notes.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"NotesManager initialized at {self.db_path}")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
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
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    completed INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 2,
                    due_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
            """)

    # ------------------------------------------------------------------ #
    # Notes
    # ------------------------------------------------------------------ #

    def add_note(self, content: str, category: str = "general") -> int:
        """Add a new note. Returns the note ID."""
        with self._conn() as conn:
            cursor = conn.execute(
                "INSERT INTO notes (content, category) VALUES (?, ?)",
                (content, category),
            )
            note_id = cursor.lastrowid
        logger.info(f"Note added #{note_id}: {content[:50]}")
        return note_id

    def get_recent_notes(self, limit: int = 10, category: Optional[str] = None) -> list[dict]:
        """Get most recent notes."""
        with self._conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM notes WHERE category=? ORDER BY created_at DESC LIMIT ?",
                    (category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM notes ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def search_notes(self, query: str) -> list[dict]:
        """Search notes by content."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM notes WHERE content LIKE ? ORDER BY created_at DESC LIMIT 10",
                (f"%{query}%",),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_note(self, note_id: int) -> bool:
        """Delete a note by ID."""
        with self._conn() as conn:
            conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        return True

    def format_notes(self, notes: list[dict]) -> str:
        """Format notes list as readable text."""
        if not notes:
            return "No notes found."
        lines = []
        for n in notes:
            date = n["created_at"][:10]
            lines.append(f"[{n['id']}] {n['content']} ({date})")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Tasks
    # ------------------------------------------------------------------ #

    def add_task(
        self,
        title: str,
        priority: int = 2,
        due_date: Optional[str] = None,
    ) -> int:
        """
        Add a task to the list.

        Args:
            title: Task description.
            priority: 1=high, 2=medium, 3=low.
            due_date: Optional due date string.

        Returns:
            Task ID.
        """
        with self._conn() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, priority, due_date) VALUES (?, ?, ?)",
                (title, priority, due_date),
            )
            task_id = cursor.lastrowid
        logger.info(f"Task added #{task_id}: {title}")
        return task_id

    def complete_task(self, task_id: int) -> bool:
        """Mark a task as completed."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE tasks SET completed=1, completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (task_id,),
            )
        logger.info(f"Task #{task_id} completed")
        return True

    def get_pending_tasks(self, limit: int = 20) -> list[dict]:
        """Get all incomplete tasks, ordered by priority."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM tasks WHERE completed=0
                   ORDER BY priority ASC, created_at ASC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_completed_tasks(self, limit: int = 10) -> list[dict]:
        """Get recently completed tasks."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM tasks WHERE completed=1
                   ORDER BY completed_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def format_tasks(self, tasks: list[dict]) -> str:
        """Format task list as readable text."""
        if not tasks:
            return "No pending tasks."
        priority_labels = {1: "HIGH", 2: "MED", 3: "LOW"}
        lines = []
        for t in tasks:
            p = priority_labels.get(t["priority"], "MED")
            due = f" (due: {t['due_date']})" if t.get("due_date") else ""
            lines.append(f"[{t['id']}] [{p}] {t['title']}{due}")
        return "\n".join(lines)

    def get_task_summary(self) -> str:
        """One-line summary for briefing."""
        tasks = self.get_pending_tasks()
        if not tasks:
            return "No pending tasks."
        high = sum(1 for t in tasks if t["priority"] == 1)
        total = len(tasks)
        if high > 0:
            return f"{total} pending task{'s' if total > 1 else ''}, {high} high priority."
        return f"{total} pending task{'s' if total > 1 else ''}."

    def get_stats(self) -> dict:
        """Return task statistics."""
        with self._conn() as conn:
            pending = conn.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE completed=0"
            ).fetchone()["c"]
            completed = conn.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE completed=1"
            ).fetchone()["c"]
            total_notes = conn.execute(
                "SELECT COUNT(*) as c FROM notes"
            ).fetchone()["c"]
        return {
            "pending_tasks": pending,
            "completed_tasks": completed,
            "total_notes": total_notes,
        }


# Module-level singleton
notes_manager = NotesManager()
