"""
projects/project_store.py
-------------------------
Persistent project storage for JOSEPH.

Manages Project records with full CRUD, search, and archive support.
All data persists to data/projects.json alongside goals, milestones, tasks, and notes.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

_DATA_FILE: Path = settings.DATA_DIR / "projects.json"


@dataclass
class Project:
    """A JOSEPH project for tracking work, goals, and research."""
    id: str
    name: str
    description: str
    path: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    status: str = "active"  # active | archived | completed
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


def _now() -> str:
    return datetime.now().isoformat()


class ProjectStore:
    """
    Persistent storage and CRUD for Project records.

    Usage:
        store = ProjectStore()
        p = store.create_project("My Project", "A description")
        projects = store.get_all_projects()
    """

    def __init__(self):
        self._projects: dict[str, Project] = {}
        self.load()

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def create_project(
        self,
        name: str,
        description: str,
        path: Optional[str] = None,
    ) -> Project:
        """
        Create a new project and persist it.

        Args:
            name: Project name.
            description: Short description of the project.
            path: Optional filesystem path associated with the project.

        Returns:
            The newly created Project.
        """
        project = Project(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            path=path,
            created_at=_now(),
            updated_at=_now(),
        )
        self._projects[project.id] = project
        self.save()
        logger.info(f"Project created: {project.name} ({project.id[:8]}...)")
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        """Retrieve a project by its ID."""
        return self._projects.get(project_id)

    def get_all_projects(self) -> list[Project]:
        """Return all projects."""
        return list(self._projects.values())

    def update_project(self, project_id: str, **kwargs) -> Project:
        """
        Update fields on an existing project.

        Args:
            project_id: The project's unique ID.
            **kwargs: Fields to update (name, description, path, status, tags, metadata).

        Returns:
            The updated Project.

        Raises:
            KeyError: If project_id is not found.
        """
        project = self._projects.get(project_id)
        if not project:
            raise KeyError(f"Project not found: {project_id}")

        allowed = {"name", "description", "path", "status", "tags", "metadata"}
        for key, value in kwargs.items():
            if key in allowed:
                setattr(project, key, value)

        project.updated_at = _now()
        self.save()
        logger.info(f"Project updated: {project.name}")
        return project

    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project by ID.

        Returns:
            True if deleted, False if not found.
        """
        if project_id in self._projects:
            del self._projects[project_id]
            self.save()
            logger.info(f"Project deleted: {project_id[:8]}...")
            return True
        return False

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #

    def search_projects(self, query: str) -> list[Project]:
        """
        Search projects by name, description, or tags.

        Args:
            query: Case-insensitive search string.

        Returns:
            Matching projects.
        """
        q = query.lower()
        results = []
        for project in self._projects.values():
            if (
                q in project.name.lower()
                or q in project.description.lower()
                or any(q in t.lower() for t in project.tags)
            ):
                results.append(project)
        return results

    def get_active_projects(self) -> list[Project]:
        """Return all projects with status='active'."""
        return [p for p in self._projects.values() if p.status == "active"]

    def archive_project(self, project_id: str) -> None:
        """Set a project's status to 'archived'."""
        self.update_project(project_id, status="archived")

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        """Persist all projects to the JSON data file."""
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = self._to_dict()
        _write_json(_DATA_FILE, data)
        logger.debug(f"Saved {len(self._projects)} projects to {_DATA_FILE}")

    def load(self) -> None:
        """Load projects from the JSON data file (if it exists)."""
        if not _DATA_FILE.exists():
            self._projects = {}
            return

        try:
            data = _read_json(_DATA_FILE)
            self._projects = self._from_dict(data)
            logger.info(f"Loaded {len(self._projects)} projects from {_DATA_FILE}")
        except Exception as e:
            logger.warning(f"Failed to load projects: {e}")
            self._projects = {}

    def _to_dict(self) -> dict:
        return {
            pid: asdict(proj)
            for pid, proj in self._projects.items()
        }

    def _from_dict(self, data: dict) -> dict[str, Project]:
        projects = {}
        for pid, fields in data.items():
            try:
                projects[pid] = Project(**fields)
            except Exception as e:
                logger.warning(f"Skipping malformed project {pid}: {e}")
        return projects


# ------------------------------------------------------------------ #
# JSON helpers (shared across sub-modules)
# ------------------------------------------------------------------ #

def _read_json(path: Path) -> dict:
    """Read and return the JSON contents of a file."""
    if not path.exists():
        return {}
    with open(str(path), "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict) -> None:
    """Write data as pretty-print JSON to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
