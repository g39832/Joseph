"""
brain/workspace_manager.py
----------------------------
Master Project Workspace — unifies goals, milestones, tasks, research,
notes, files, knowledge graph links, and activity history into a single
workspace per project.

All data lives under data/workspaces/<project_id>/.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

WORKSPACE_DIR: Path = settings.DATA_DIR / "workspaces"


@dataclass
class WorkspaceFile:
    path: str
    description: str = ""
    added_at: str = ""

    def __post_init__(self):
        if not self.added_at:
            self.added_at = datetime.now().isoformat()


@dataclass
class KGLink:
    node_id: str
    node_label: str = ""
    relation: str = "related"
    linked_at: str = ""

    def __post_init__(self):
        if not self.linked_at:
            self.linked_at = datetime.now().isoformat()


@dataclass
class WorkspaceData:
    project_id: str
    project_name: str = ""
    goals: list[dict] = field(default_factory=list)
    milestones: list[dict] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    research_entries: list[dict] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)
    kg_links: list[dict] = field(default_factory=list)
    activity_log: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    lessons: list[dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class WorkspaceManager:
    """
    Unified workspace for each project.

    Wraps ProjectStore, GoalTracker, MilestoneTracker, TaskManager,
    NotesManager, ResearchWorkspace into a single view.

    Usage:
        wm = WorkspaceManager(project_store, goal_tracker, ...)
        ws = wm.get_workspace("proj-123")
        ws.tasks  # list of task dicts
        ws.add_note("proj-123", "Some note")
    """

    def __init__(
        self,
        project_store=None,
        goal_tracker=None,
        milestone_tracker=None,
        task_manager=None,
        notes_manager=None,
        research_workspace=None,
    ):
        self._ps = project_store
        self._gt = goal_tracker
        self._mt = milestone_tracker
        self._tm = task_manager
        self._nm = notes_manager
        self._rw = research_workspace
        self._cache: dict[str, WorkspaceData] = {}

    def get_workspace(self, project_id: str) -> Optional[WorkspaceData]:
        """Build a unified workspace view from all sources."""
        if project_id in self._cache:
            return self._cache[project_id]

        try:
            proj = self._ps.get_project(project_id) if self._ps else None
            if not proj:
                return None
        except Exception:
            return None

        goals = []
        if self._gt:
            try:
                for g in self._gt.get_goals(project_id=project_id):
                    goals.append(self._safe_asdict(g))
            except Exception:
                pass

        milestones = []
        if self._mt:
            try:
                for m in self._mt.get_milestones(project_id=project_id):
                    milestones.append(self._safe_asdict(m))
            except Exception:
                pass

        tasks = []
        if self._tm:
            try:
                for t in self._tm.get_tasks(project_id=project_id):
                    tasks.append(self._safe_asdict(t))
            except Exception:
                pass

        research_entries = []
        if self._rw:
            try:
                for e in self._rw.get_by_project(project_id):
                    research_entries.append(self._safe_asdict(e))
            except Exception:
                pass

        notes = []
        if self._nm:
            try:
                for n in self._nm.get_notes(project_id=project_id):
                    notes.append(self._safe_asdict(n))
            except Exception:
                pass

        ws = WorkspaceData(
            project_id=project_id,
            project_name=proj.name,
            goals=goals,
            milestones=milestones,
            tasks=tasks,
            research_entries=research_entries,
            notes=notes,
        )

        # Merge persisted workspace extras
        persisted = self._load_persisted(project_id)
        if persisted:
            ws.files = persisted.get("files", [])
            ws.kg_links = persisted.get("kg_links", [])
            ws.activity_log = persisted.get("activity_log", [])
            ws.decisions = persisted.get("decisions", [])
            ws.lessons = persisted.get("lessons", [])

        self._cache[project_id] = ws
        return ws

    def add_note(self, project_id: str, content: str, title: str = "") -> bool:
        if not self._nm:
            return False
        try:
            self._nm.add_note(project_id=project_id, content=content, title=title)
            self._invalidate(project_id)
            return True
        except Exception as e:
            logger.warning(f"add_note failed: {e}")
            return False

    def add_file(self, project_id: str, path: str, description: str = "") -> None:
        data = self._load_persisted(project_id)
        data.setdefault("files", []).append({
            "path": path,
            "description": description,
            "added_at": datetime.now().isoformat(),
        })
        self._save_persisted(project_id, data)
        self._invalidate(project_id)

    def add_kg_link(
        self, project_id: str, node_id: str,
        node_label: str = "", relation: str = "related",
    ) -> None:
        data = self._load_persisted(project_id)
        data.setdefault("kg_links", []).append({
            "node_id": node_id,
            "node_label": node_label,
            "relation": relation,
            "linked_at": datetime.now().isoformat(),
        })
        self._save_persisted(project_id, data)
        self._invalidate(project_id)

    def log_activity(
        self, project_id: str, entry_type: str, summary: str,
    ) -> None:
        data = self._load_persisted(project_id)
        data.setdefault("activity_log", []).append({
            "type": entry_type,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep last 200
        log = data["activity_log"]
        if len(log) > 200:
            data["activity_log"] = log[-200:]
        self._save_persisted(project_id, data)
        self._invalidate(project_id)

    def add_decision(
        self, project_id: str, title: str, description: str,
        rationale: str = "",
    ) -> None:
        data = self._load_persisted(project_id)
        data.setdefault("decisions", []).append({
            "title": title,
            "description": description,
            "rationale": rationale,
            "timestamp": datetime.now().isoformat(),
        })
        self._save_persisted(project_id, data)
        self._invalidate(project_id)

    def add_lesson(self, project_id: str, lesson: str) -> None:
        data = self._load_persisted(project_id)
        data.setdefault("lessons", []).append({
            "lesson": lesson,
            "timestamp": datetime.now().isoformat(),
        })
        self._save_persisted(project_id, data)
        self._invalidate(project_id)

    def get_summary(self, project_id: str) -> str:
        ws = self.get_workspace(project_id)
        if not ws:
            return ""
        lines = [f"Workspace: {ws.project_name}"]
        if ws.goals:
            active = [g for g in ws.goals if g.get("status") == "active"]
            if active:
                lines.append(f"  Active goals: {len(active)}")
        if ws.milestones:
            upcoming = [m for m in ws.milestones if m.get("status") != "completed"]
            lines.append(f"  Milestones: {len(upcoming)} pending")
        if ws.tasks:
            open_t = [t for t in ws.tasks if t.get("status") != "done"]
            lines.append(f"  Tasks: {len(open_t)} open")
        if ws.research_entries:
            lines.append(f"  Research entries: {len(ws.research_entries)}")
        if ws.files:
            lines.append(f"  Files: {len(ws.files)}")
        if ws.decisions:
            lines.append(f"  Decisions: {len(ws.decisions)}")
        if ws.lessons:
            lines.append(f"  Lessons learned: {len(ws.lessons)}")
        return "\n".join(lines)

    def _invalidate(self, project_id: str) -> None:
        self._cache.pop(project_id, None)

    def _load_persisted(self, project_id: str) -> dict:
        path = WORKSPACE_DIR / f"{project_id}.json"
        if not path.exists():
            return {}
        try:
            with open(str(path), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_persisted(self, project_id: str, data: dict) -> None:
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        path = WORKSPACE_DIR / f"{project_id}.json"
        with open(str(path), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _safe_asdict(obj) -> dict:
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        if isinstance(obj, dict):
            return obj
        return {"error": "cannot serialize"}
