"""
projects/milestone_tracker.py
-----------------------------
Milestone tracking for JOSEPH projects.

Milestones represent key checkpoints within a project,
optionally linked to a specific goal.
"""

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional

from projects.project_store import _read_json, _write_json
from configs.settings import settings

logger = logging.getLogger(__name__)

_DATA_FILE = settings.DATA_DIR / "projects.json"
_STORAGE_KEY = "milestones"


@dataclass
class Milestone:
    """A checkpoint or key event within a project."""
    id: str
    project_id: str
    title: str
    description: str = ""
    deadline: Optional[str] = None
    goal_id: Optional[str] = None
    status: str = "pending"  # pending | reached | missed
    reached_at: Optional[str] = None
    criteria: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now().isoformat()


class MilestoneTracker:
    """
    Manages milestones within projects.

    Usage:
        tracker = MilestoneTracker()
        m = tracker.add_milestone(project_id, "Beta Launch", deadline="2026-06-01")
        tracker.reached_milestone(m.id)
        upcoming = tracker.get_upcoming_milestones(days=30)
    """

    def __init__(self):
        self._milestones: dict[str, Milestone] = {}
        self.load()

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def add_milestone(
        self,
        project_id: str,
        title: str,
        description: str = "",
        deadline: Optional[str] = None,
        goal_id: Optional[str] = None,
    ) -> Milestone:
        """
        Add a new milestone to a project.

        Args:
            project_id: The owning project's ID.
            title: Milestone name.
            description: Optional description.
            deadline: Optional ISO date string.
            goal_id: Optional goal ID this milestone is linked to.

        Returns:
            The newly created Milestone.
        """
        milestone = Milestone(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title=title,
            description=description,
            deadline=deadline,
            goal_id=goal_id,
        )
        self._milestones[milestone.id] = milestone
        self.save()
        logger.info(f"Milestone added: {milestone.title} ({milestone.id[:8]}...)")
        return milestone

    def reached_milestone(self, milestone_id: str) -> None:
        """Mark a milestone as reached with a timestamp."""
        milestone = self._milestones.get(milestone_id)
        if not milestone:
            raise KeyError(f"Milestone not found: {milestone_id}")
        milestone.status = "reached"
        milestone.reached_at = _now()
        self.save()
        logger.info(f"Milestone reached: {milestone.title}")

    def get_milestones(self, project_id: str) -> list[Milestone]:
        """Get all milestones for a project."""
        return [
            m for m in self._milestones.values()
            if m.project_id == project_id
        ]

    def get_milestone(self, milestone_id: str) -> Optional[Milestone]:
        """Retrieve a single milestone by ID."""
        return self._milestones.get(milestone_id)

    def update_milestone(self, milestone_id: str, **kwargs) -> Milestone:
        """Update fields on an existing milestone."""
        milestone = self._milestones.get(milestone_id)
        if not milestone:
            raise KeyError(f"Milestone not found: {milestone_id}")

        allowed = {"title", "description", "deadline", "goal_id", "status", "criteria"}
        for key, value in kwargs.items():
            if key in allowed:
                setattr(milestone, key, value)

        self.save()
        return milestone

    def delete_milestone(self, milestone_id: str) -> bool:
        """Delete a milestone by ID. Returns True if deleted."""
        if milestone_id in self._milestones:
            del self._milestones[milestone_id]
            self.save()
            return True
        return False

    def miss_milestone(self, milestone_id: str) -> None:
        """Mark a milestone as missed."""
        milestone = self._milestones.get(milestone_id)
        if not milestone:
            raise KeyError(f"Milestone not found: {milestone_id}")
        milestone.status = "missed"
        self.save()
        logger.info(f"Milestone missed: {milestone.title}")

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_upcoming_milestones(self, days: int = 30) -> list[Milestone]:
        """
        Return pending milestones with deadlines within the next N days.

        Args:
            days: How many days ahead to look (default 30).

        Returns:
            List of matching Milestones.
        """
        now = datetime.now()
        cutoff = now + timedelta(days=days)
        results = []
        for m in self._milestones.values():
            if m.status != "pending" or not m.deadline:
                continue
            try:
                dl = datetime.fromisoformat(m.deadline)
                if now <= dl <= cutoff:
                    results.append(m)
            except (ValueError, TypeError):
                continue
        return sorted(results, key=lambda x: x.deadline or "")

    def get_overdue_milestones(self) -> list[Milestone]:
        """
        Return pending milestones past their deadline.

        Returns:
            List of overdue Milestones.
        """
        now = datetime.now()
        results = []
        for m in self._milestones.values():
            if m.status != "pending" or not m.deadline:
                continue
            try:
                dl = datetime.fromisoformat(m.deadline)
                if dl < now:
                    results.append(m)
            except (ValueError, TypeError):
                continue
        return sorted(results, key=lambda x: x.deadline or "")

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        """Persist milestones to the shared JSON data file."""
        all_data = _read_json(_DATA_FILE)
        all_data[_STORAGE_KEY] = {
            mid: asdict(m) for mid, m in self._milestones.items()
        }
        _write_json(_DATA_FILE, all_data)
        logger.debug(f"Saved {len(self._milestones)} milestones")

    def load(self) -> None:
        """Load milestones from the shared JSON data file."""
        if not _DATA_FILE.exists():
            self._milestones = {}
            return

        try:
            all_data = _read_json(_DATA_FILE)
            raw = all_data.get(_STORAGE_KEY, {})
            self._milestones = {}
            for mid, fields in raw.items():
                try:
                    self._milestones[mid] = Milestone(**fields)
                except Exception as e:
                    logger.warning(f"Skipping malformed milestone {mid}: {e}")
            logger.info(f"Loaded {len(self._milestones)} milestones")
        except Exception as e:
            logger.warning(f"Failed to load milestones: {e}")
            self._milestones = {}
