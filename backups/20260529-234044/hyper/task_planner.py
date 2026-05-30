"""
hyper/task_planner.py
---------------------
Persistent task planning with dependency tracking and progress reporting.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.DATA_DIR / "hyper_tasks.db"


class TaskPlanner:
    """Breaks goals into tracked plans and subtasks."""

    def __init__(self, llm=None, memory=None, db_path: Optional[Path] = None):
        self.llm = llm
        self.memory = memory
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
                conn = sqlite3.connect(str(self.db_path))
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
                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    progress REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS plan_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    step_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    depends_on INTEGER DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(plan_id) REFERENCES plans(id)
                );

                CREATE INDEX IF NOT EXISTS idx_plan_steps_plan_id
                    ON plan_steps(plan_id);
            """)
        except Exception as e:
            logger.warning(f"TaskPlanner falling back to in-memory store: {e}")
            self._use_memory_store = True
            with self._conn() as conn:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    progress REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS plan_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    step_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    depends_on INTEGER DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(plan_id) REFERENCES plans(id)
                );

                CREATE INDEX IF NOT EXISTS idx_plan_steps_plan_id
                    ON plan_steps(plan_id);
            """)

    def _heuristic_steps(self, goal: str) -> list[str]:
        goal = goal.strip()
        if not goal:
            return []

        raw_parts = []
        separators = [" and then ", " then ", " after that ", ";", " and "]
        working = [goal]
        for sep in separators:
            next_working = []
            for item in working:
                if sep in item.lower():
                    pieces = [p.strip() for p in item.split(sep) if p.strip()]
                    next_working.extend(pieces)
                else:
                    next_working.append(item)
            working = next_working
        raw_parts = working

        if len(raw_parts) == 1:
            raw_parts = [goal]
        return raw_parts[:5]

    def create_plan(self, goal: str, max_steps: int = 5) -> dict:
        """Create and persist a plan for a goal."""
        steps = []

        if self.llm:
            try:
                prompt = f"""Break this goal into at most {max_steps} clear steps.
Return only one step per line, no numbering, no extra commentary.

Goal: {goal}
Steps:"""
                raw = self.llm.generate(prompt, temperature=0.15)
                steps = [line.strip("- ").strip() for line in raw.splitlines() if line.strip()]
            except Exception as e:
                logger.debug(f"LLM plan generation failed: {e}")

        if not steps:
            steps = self._heuristic_steps(goal)

        steps = steps[:max_steps] or [goal]

        with self._conn() as conn:
            cur = conn.execute("INSERT INTO plans (goal) VALUES (?)", (goal,))
            plan_id = cur.lastrowid
            for index, step in enumerate(steps, start=1):
                conn.execute(
                    """INSERT INTO plan_steps (plan_id, step_index, title, details, status, depends_on)
                       VALUES (?, ?, ?, ?, 'pending', ?)""",
                    (plan_id, index, step, "", index - 1 if index > 1 else None),
                )

        return self.get_plan(plan_id)

    def get_plan(self, plan_id: int) -> dict:
        with self._conn() as conn:
            plan = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if not plan:
                return {}
            steps = conn.execute(
                "SELECT * FROM plan_steps WHERE plan_id = ? ORDER BY step_index",
                (plan_id,),
            ).fetchall()

        return {
            "id": plan["id"],
            "goal": plan["goal"],
            "status": plan["status"],
            "progress": plan["progress"],
            "created_at": plan["created_at"],
            "updated_at": plan["updated_at"],
            "steps": [dict(step) for step in steps],
        }

    def update_step_status(self, plan_id: int, step_index: int, status: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                """UPDATE plan_steps
                   SET status = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE plan_id = ? AND step_index = ?""",
                (status, plan_id, step_index),
            )
            if cur.rowcount == 0:
                return False
            self._recalculate_progress(conn, plan_id)
            return True

    def _recalculate_progress(self, conn, plan_id: int) -> None:
        rows = conn.execute(
            "SELECT status FROM plan_steps WHERE plan_id = ?",
            (plan_id,),
        ).fetchall()
        if not rows:
            return
        done = sum(1 for row in rows if row["status"] == "done")
        progress = round(done / len(rows), 3)
        status = "complete" if progress >= 1.0 else "active"
        conn.execute(
            """UPDATE plans
               SET progress = ?, status = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (progress, status, plan_id),
        )

    def get_active_plans(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id FROM plans WHERE status != 'complete' ORDER BY updated_at DESC"
            ).fetchall()
        return [self.get_plan(row["id"]) for row in rows]

    def suggest_next_step(self, plan_id: int) -> Optional[dict]:
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        for step in plan["steps"]:
            if step["status"] == "pending":
                return step
        return None

    def get_progress_report(self, plan_id: int) -> str:
        plan = self.get_plan(plan_id)
        if not plan:
            return "Plan not found."
        lines = [f"Plan {plan['id']}: {plan['goal']}", f"Progress: {round(plan['progress'] * 100)}%"]
        for step in plan["steps"]:
            lines.append(f"- [{step['status']}] {step['title']}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"TaskPlanner(db={self.db_path.name})"
