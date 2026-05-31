"""
brain/project_awareness.py
---------------------------
Advanced project awareness for JOSEPH.

Automatically detects when user input relates to an active project
and injects relevant project context (goals, milestones, tasks,
research notes) into the LLM context.

Uses fast keyword matching — no LLM calls required.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class ProjectAwareness:
    """
    Matches user input to active projects and builds context.

    Usage:
        awareness = ProjectAwareness(project_manager)
        ctx = awareness.get_context("how is the cancer simulation going?")
        # Returns project context or empty string
    """

    def __init__(self, project_manager=None):
        self._pm = project_manager

    def get_context(self, user_input: str, max_projects: int = 2) -> str:
        if not self._pm:
            return ""

        try:
            # Get all active projects
            projects = self._pm.project_store.get_active_projects()
            if not projects:
                return ""
        except Exception:
            return ""

        user_lower = user_input.lower()
        matched = []

        for proj in projects:
            score = 0
            name_lower = proj.name.lower()
            desc_lower = proj.description.lower()

            # Direct name match (highest weight)
            for word in name_lower.split():
                if word in user_lower and len(word) > 2:
                    score += 3

            # Tag match
            for tag in proj.tags:
                if tag.lower() in user_lower:
                    score += 2

            # Description keyword match
            for word in desc_lower.split():
                if word in user_lower and len(word) > 3:
                    score += 1

            if score > 0:
                matched.append((proj, score))

        if not matched:
            return ""

        matched.sort(key=lambda x: -x[1])
        matched = matched[:max_projects]

        sections = []
        for proj, _score in matched:
            parts = [f"Project: {proj.name}"]
            if proj.description:
                parts.append(f"  Description: {proj.description}")
            if proj.status:
                parts.append(f"  Status: {proj.status}")

            # Get goals
            try:
                goals = self._pm.goal_tracker.get_goals(project_id=proj.id)
                if goals:
                    active_goals = [g for g in goals if g.status == "active"]
                    if active_goals:
                        parts.append("  Goals:")
                        for g in active_goals[:3]:
                            parts.append(f"    - {g.title}")
            except Exception:
                pass

            # Get milestones
            try:
                milestones = self._pm.milestone_tracker.get_milestones(
                    project_id=proj.id
                )
                if milestones:
                    upcoming = [
                        m for m in milestones if m.status != "completed"
                    ]
                    if upcoming:
                        parts.append("  Active Milestones:")
                        for m in upcoming[:2]:
                            parts.append(f"    - {m.title}")
            except Exception:
                pass

            # Get open tasks
            try:
                tasks = self._pm.task_manager.get_tasks(project_id=proj.id)
                if tasks:
                    open_tasks = [t for t in tasks if t.status != "done"]
                    if open_tasks:
                        parts.append(
                            f"  Open Tasks: {len(open_tasks)}"
                        )
                        for t in open_tasks[:3]:
                            parts.append(f"    - {t.title}")
            except Exception:
                pass

            sections.append("\n".join(parts))

        if not sections:
            return ""

        return "## Relevant Project Context\n" + "\n\n".join(sections)

    def get_all_projects_summary(self) -> str:
        """Brief summary of all active projects for daily briefing."""
        if not self._pm:
            return ""
        try:
            projects = self._pm.project_store.get_active_projects()
            if not projects:
                return ""
            lines = ["Active projects:"]
            for p in projects:
                try:
                    tasks = self._pm.task_manager.get_tasks(project_id=p.id)
                    open_tasks = len(
                        [t for t in tasks if t.status != "done"]
                    ) if tasks else 0
                except Exception:
                    open_tasks = 0
                lines.append(
                    f"  - {p.name} ({p.status}, {open_tasks} open tasks)"
                )
            return "\n".join(lines)
        except Exception:
            return ""
