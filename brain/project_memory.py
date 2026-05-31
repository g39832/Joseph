"""
brain/project_memory.py
-------------------------
Project Memory — makes memories project-aware.

When discussing a project, automatically retrieves project-specific
context including decisions, research, tasks, milestones, and lessons learned.

Wraps MemoryManager to add project-aware retrieval.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ProjectMemory:
    """
    Project-aware memory retrieval.

    Usage:
        pm = ProjectMemory(memory_manager, workspace_manager)
        ctx = pm.get_project_context("proj-123")
    """

    def __init__(self, memory_manager=None, workspace_manager=None, project_store=None):
        self._memory = memory_manager
        self._wm = workspace_manager
        self._ps = project_store

    def get_project_context(self, project_id: str) -> str:
        """Build a project-specific context string for LLM injection."""
        ws = self._get_ws(project_id)
        if not ws:
            return ""

        parts = [f"# Project: {ws.project_name}"]

        # Decisions
        if ws.decisions:
            parts.append("## Decisions")
            for d in ws.decisions[-5:]:
                parts.append(f"- {d.get('title', '')}: {d.get('description', '')[:100]}")
                if d.get("rationale"):
                    parts.append(f"  Rationale: {d['rationale'][:100]}")

        # Lessons
        if ws.lessons:
            parts.append("## Lessons Learned")
            for l in ws.lessons[-5:]:
                parts.append(f"- {l.get('lesson', '')[:120]}")

        # Recent activity
        if ws.activity_log:
            parts.append("## Recent Activity")
            for a in ws.activity_log[-5:]:
                parts.append(f"- [{a.get('type', '')}] {a.get('summary', '')[:80]}")

        # Open tasks
        open_tasks = [t for t in ws.tasks if t.get("status") != "done"]
        if open_tasks:
            parts.append("## Open Tasks")
            for t in open_tasks[:5]:
                parts.append(f"- {t.get('title', 'Untitled')}")

        # Milestone status
        pending_m = [m for m in ws.milestones if m.get("status") != "completed"]
        if pending_m:
            parts.append("## Pending Milestones")
            for m in pending_m[:3]:
                due = m.get("target_date") or m.get("deadline", "no date")
                parts.append(f"- {m.get('title', 'Untitled')} (due {due})")

        return "\n".join(parts)

    def get_memory_context(
        self, user_input: str, active_project_id: Optional[str] = None,
    ) -> str:
        """
        Full context: general memory + project-specific if a project is active.

        Call from _llm_worker to augment memory_context.
        """
        parts = []
        if self._memory:
            try:
                general = self._memory.get_context_for_llm(query=user_input)
                if general:
                    parts.append(general)
            except Exception:
                pass

        if active_project_id:
            proj_ctx = self.get_project_context(active_project_id)
            if proj_ctx:
                parts.append(proj_ctx)

        return "\n\n".join(parts) if parts else ""

    def find_project_for_input(
        self, user_input: str, project_store=None,
    ) -> Optional[str]:
        """
        Detect which project the user is referring to.
        Uses keyword matching — no LLM.
        """
        if not project_store:
            return None

        user_lower = user_input.lower()
        best_match = None
        best_score = 0

        try:
            for proj in project_store.get_active_projects():
                score = 0
                if proj.name.lower() in user_lower:
                    score += 5
                for word in proj.name.lower().split():
                    if len(word) > 3 and word in user_lower:
                        score += 2
                if score > best_score:
                    best_score = score
                    best_match = proj.id
        except Exception:
            pass

        return best_match if best_score >= 3 else None

    def save_memory(
        self, project_id: str, memory_manager, text: str,
    ) -> bool:
        """Save a project-specific memory."""
        if not memory_manager:
            return False
        try:
            tagged = f"[project:{project_id[:8]}] {text}"
            memory_manager.save_explicit_memory(tagged)
            return True
        except Exception:
            return False

    def _get_ws(self, project_id: str):
        if not self._wm:
            return None
        try:
            return self._wm.get_workspace(project_id)
        except Exception:
            return None
