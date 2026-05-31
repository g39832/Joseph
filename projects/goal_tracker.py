"""
projects/goal_tracker.py
------------------------
Goal tracking for JOSEPH projects.

Each goal belongs to a project and tracks priority, status, and deadlines.
Persists alongside other project data in data/projects.json.
"""

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from projects.project_store import _read_json, _write_json
from configs.settings import settings

logger = logging.getLogger(__name__)

_DATA_FILE = settings.DATA_DIR / "projects.json"
_STORAGE_KEY = "goals"


@dataclass
class Goal:
    """A goal associated with a project."""
    id: str
    project_id: str
    title: str
    description: str = ""
    priority: str = "medium"  # low | medium | high | critical
    status: str = "not_started"  # not_started | in_progress | completed | cancelled
    deadline: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None
    tags: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now().isoformat()


class GoalTracker:
    """
    Manages goals within projects.

    Usage:
        tracker = GoalTracker()
        goal = tracker.add_goal(project_id, "Launch v1.0", priority="high")
        stats = tracker.get_goal_stats(project_id)
    """

    def __init__(self):
        self._goals: dict[str, Goal] = {}
        self.load()

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def add_goal(
        self,
        project_id: str,
        title: str,
        description: str = "",
        priority: str = "medium",
        deadline: Optional[str] = None,
    ) -> Goal:
        """
        Add a new goal to a project.

        Args:
            project_id: The owning project's ID.
            title: Goal title.
            description: Optional detailed description.
            priority: low, medium, high, or critical.
            deadline: Optional ISO date string.

        Returns:
            The newly created Goal.
        """
        goal = Goal(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            deadline=deadline,
            created_at=_now(),
        )
        self._goals[goal.id] = goal
        self.save()
        logger.info(f"Goal added: {goal.title} ({goal.id[:8]}...)")
        return goal

    def get_goals(self, project_id: str) -> list[Goal]:
        """Get all goals for a given project."""
        return [g for g in self._goals.values() if g.project_id == project_id]

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Retrieve a single goal by ID."""
        return self._goals.get(goal_id)

    def update_goal(self, goal_id: str, **kwargs) -> Goal:
        """
        Update fields on an existing goal.

        Args:
            goal_id: The goal's unique ID.
            **kwargs: Fields to update.

        Returns:
            The updated Goal.

        Raises:
            KeyError: If goal_id is not found.
        """
        goal = self._goals.get(goal_id)
        if not goal:
            raise KeyError(f"Goal not found: {goal_id}")

        allowed = {"title", "description", "priority", "status", "deadline", "tags"}
        for key, value in kwargs.items():
            if key in allowed:
                setattr(goal, key, value)

        self.save()
        logger.info(f"Goal updated: {goal.title}")
        return goal

    def complete_goal(self, goal_id: str) -> None:
        """Mark a goal as completed with a timestamp."""
        self.update_goal(goal_id, status="completed", completed_at=_now())

    def delete_goal(self, goal_id: str) -> bool:
        """Delete a goal by ID. Returns True if deleted."""
        if goal_id in self._goals:
            del self._goals[goal_id]
            self.save()
            logger.info(f"Goal deleted: {goal_id[:8]}...")
            return True
        return False

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #

    def get_goal_stats(self, project_id: str) -> dict:
        """
        Return counts of goals by status and priority for a project.

        Returns:
            {
                "total": int,
                "by_status": {"not_started": ..., "in_progress": ..., ...},
                "by_priority": {"low": ..., "medium": ..., ...}
            }
        """
        goals = self.get_goals(project_id)
        by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for g in goals:
            by_status[g.status] = by_status.get(g.status, 0) + 1
            by_priority[g.priority] = by_priority.get(g.priority, 0) + 1
        return {
            "total": len(goals),
            "by_status": by_status,
            "by_priority": by_priority,
        }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        """Persist goals to the shared JSON data file."""
        all_data = _read_json(_DATA_FILE)
        all_data[_STORAGE_KEY] = {
            gid: asdict(g) for gid, g in self._goals.items()
        }
        _write_json(_DATA_FILE, all_data)
        logger.debug(f"Saved {len(self._goals)} goals")

    def load(self) -> None:
        """Load goals from the shared JSON data file."""
        if not _DATA_FILE.exists():
            self._goals = {}
            return

        try:
            all_data = _read_json(_DATA_FILE)
            raw = all_data.get(_STORAGE_KEY, {})
            self._goals = {}
            for gid, fields in raw.items():
                try:
                    self._goals[gid] = Goal(**fields)
                except Exception as e:
                    logger.warning(f"Skipping malformed goal {gid}: {e}")
            logger.info(f"Loaded {len(self._goals)} goals")
        except Exception as e:
            logger.warning(f"Failed to load goals: {e}")
            self._goals = {}
