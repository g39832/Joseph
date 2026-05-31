"""
projects/task_manager.py
-------------------------
Task management for JOSEPH projects.

ProjectTasks are fine-grained work items within a project,
optionally linked to a goal and with dependency tracking.
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
_STORAGE_KEY = "tasks"


@dataclass
class ProjectTask:
    """A task belonging to a project."""
    id: str
    project_id: str
    title: str
    description: str = ""
    status: str = "todo"  # todo | in_progress | done | cancelled
    priority: str = "medium"  # low | medium | high | critical
    created_at: str = ""
    due_date: Optional[str] = None
    goal_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now().isoformat()


class TaskManager:
    """
    Manages tasks within projects.

    Usage:
        tm = TaskManager()
        task = tm.add_task(project_id, "Write tests", priority="high")
        tm.complete_task(task.id)
        blocked = tm.get_blocked_tasks()
    """

    def __init__(self):
        self._tasks: dict[str, ProjectTask] = {}
        self.load()

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def add_task(
        self,
        project_id: str,
        title: str,
        description: str = "",
        priority: str = "medium",
        due_date: Optional[str] = None,
        goal_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        depends_on: Optional[list[str]] = None,
    ) -> ProjectTask:
        """
        Add a new task to a project.

        Args:
            project_id: The owning project's ID.
            title: Task title.
            description: Optional description.
            priority: low, medium, high, or critical.
            due_date: Optional ISO date string.
            goal_id: Optional goal to link this task to.
            tags: Optional list of tag strings.
            depends_on: Optional list of task IDs this task depends on.

        Returns:
            The newly created ProjectTask.
        """
        task = ProjectTask(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            goal_id=goal_id,
            tags=tags or [],
            depends_on=depends_on or [],
            created_at=_now(),
        )
        self._tasks[task.id] = task
        self.save()
        logger.info(f"Task added: {task.title} ({task.id[:8]}...)")
        return task

    def get_task(self, task_id: str) -> Optional[ProjectTask]:
        """Retrieve a single task by ID."""
        return self._tasks.get(task_id)

    def get_tasks(self, project_id: str, status: Optional[str] = None) -> list[ProjectTask]:
        """
        Get tasks for a project, optionally filtered by status.

        Args:
            project_id: The project to query.
            status: Optional status filter (todo, in_progress, done, cancelled).

        Returns:
            List of matching ProjectTasks.
        """
        tasks = [t for t in self._tasks.values() if t.project_id == project_id]
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at or "", reverse=True)

    def update_task(self, task_id: str, **kwargs) -> ProjectTask:
        """
        Update fields on an existing task.

        Args:
            task_id: The task's unique ID.
            **kwargs: Fields to update.

        Returns:
            The updated ProjectTask.

        Raises:
            KeyError: If task_id is not found.
        """
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task not found: {task_id}")

        allowed = {
            "title", "description", "status", "priority",
            "due_date", "goal_id", "tags", "depends_on",
        }
        for key, value in kwargs.items():
            if key in allowed:
                setattr(task, key, value)

        self.save()
        logger.info(f"Task updated: {task.title}")
        return task

    def complete_task(self, task_id: str) -> None:
        """Mark a task as done."""
        self.update_task(task_id, status="done")

    def delete_task(self, task_id: str) -> bool:
        """Delete a task by ID. Returns True if deleted."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self.save()
            logger.info(f"Task deleted: {task_id[:8]}...")
            return True
        return False

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_task_stats(self, project_id: str) -> dict:
        """
        Return task statistics for a project.

        Returns:
            {
                "total": int,
                "by_status": {"todo": ..., "in_progress": ..., ...},
                "by_priority": {"low": ..., "medium": ..., ...},
                "blocked": int
            }
        """
        tasks = self.get_tasks(project_id)
        by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for t in tasks:
            by_status[t.status] = by_status.get(t.status, 0) + 1
            by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        blocked = sum(
            1 for t in tasks
            if t.depends_on and any(
                self._tasks.get(dep) and self._tasks[dep].status != "done"
                for dep in t.depends_on
            )
        )
        return {
            "total": len(tasks),
            "by_status": by_status,
            "by_priority": by_priority,
            "blocked": blocked,
        }

    def get_blocked_tasks(self) -> list[ProjectTask]:
        """
        Return all tasks whose dependencies are not yet done.

        A task is "blocked" when any of its depends_on IDs reference
        a task that exists and is not in "done" status.
        """
        blocked = []
        for task in self._tasks.values():
            if not task.depends_on:
                continue
            for dep_id in task.depends_on:
                dep = self._tasks.get(dep_id)
                if dep and dep.status != "done":
                    blocked.append(task)
                    break
        return blocked

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        """Persist tasks to the shared JSON data file."""
        all_data = _read_json(_DATA_FILE)
        all_data[_STORAGE_KEY] = {
            tid: asdict(t) for tid, t in self._tasks.items()
        }
        _write_json(_DATA_FILE, all_data)
        logger.debug(f"Saved {len(self._tasks)} tasks")

    def load(self) -> None:
        """Load tasks from the shared JSON data file."""
        if not _DATA_FILE.exists():
            self._tasks = {}
            return

        try:
            all_data = _read_json(_DATA_FILE)
            raw = all_data.get(_STORAGE_KEY, {})
            self._tasks = {}
            for tid, fields in raw.items():
                try:
                    self._tasks[tid] = ProjectTask(**fields)
                except Exception as e:
                    logger.warning(f"Skipping malformed task {tid}: {e}")
            logger.info(f"Loaded {len(self._tasks)} tasks")
        except Exception as e:
            logger.warning(f"Failed to load tasks: {e}")
            self._tasks = {}
