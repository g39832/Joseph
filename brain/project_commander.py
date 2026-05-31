"""
brain/project_commander.py
----------------------------
Project Commander — understands project status, tracks progress,
recommends next actions, detects blockers, and generates summaries.

No LLM calls — purely rule-based for speed.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ProjectCommander:
    """
    Analyzes a workspace and provides status, recommendations, blockers.

    Usage:
        pc = ProjectCommander(workspace_manager)
        status = pc.get_status("proj-123")
        next_actions = pc.recommend_next("proj-123")
        summary = pc.summarize("proj-123")
    """

    def __init__(self, workspace_manager=None):
        self._wm = workspace_manager

    def get_status(self, project_id: str) -> dict:
        """Return structured status report for a project."""
        ws = self._get_ws(project_id)
        if not ws:
            return {"error": "project not found"}

        active_goals = [g for g in ws.goals if g.get("status") == "active"]
        pending_milestones = [
            m for m in ws.milestones if m.get("status") != "completed"
        ]
        open_tasks = [t for t in ws.tasks if t.get("status") != "done"]
        completed_tasks = [t for t in ws.tasks if t.get("status") == "done"]
        total_tasks = len(ws.tasks)

        progress = 0
        if total_tasks:
            progress = int((len(completed_tasks) / total_tasks) * 100)

        return {
            "project": ws.project_name,
            "active_goals": len(active_goals),
            "total_goals": len(ws.goals),
            "pending_milestones": len(pending_milestones),
            "total_milestones": len(ws.milestones),
            "open_tasks": len(open_tasks),
            "completed_tasks": len(completed_tasks),
            "total_tasks": total_tasks,
            "progress_pct": progress,
            "research_entries": len(ws.research_entries),
            "decisions": len(ws.decisions),
            "lessons": len(ws.lessons),
        }

    def detect_blockers(self, project_id: str) -> list[str]:
        """Identify blocking issues."""
        ws = self._get_ws(project_id)
        if not ws:
            return []

        blockers = []

        # No active goals but has tasks
        active_goals = [g for g in ws.goals if g.get("status") == "active"]
        open_tasks = [t for t in ws.tasks if t.get("status") != "done"]
        if not active_goals and open_tasks:
            blockers.append("No active goals defined for open tasks")

        # Overdue milestones
        now = datetime.now().isoformat()[:10]
        for m in ws.milestones:
            due = m.get("target_date") or m.get("deadline")
            if due and due < now and m.get("status") != "completed":
                blockers.append(f"Overdue milestone: {m.get('title', 'Untitled')}")

        # Stalled tasks (created long ago, not started)
        for t in open_tasks:
            created = t.get("created_at", "")
            if created and created[:10] < now:
                status = t.get("status", "")
                if status in ("", "backlog", "todo"):
                    blockers.append(f"Unstarted task: {t.get('title', 'Untitled')}")

        # Tasks with no assignee/status
        stalled = [
            t for t in open_tasks
            if not t.get("status") or t.get("status") == "backlog"
        ]
        if len(stalled) > 3:
            blockers.append(f"{len(stalled)} tasks in backlog without status")

        # No research for a research-heavy project
        if not ws.research_entries and any(
            "research" in g.get("title", "").lower() for g in ws.goals
        ):
            blockers.append("Research goal has no research entries")

        return blockers[:5]

    def recommend_next(self, project_id: str, max_items: int = 5) -> list[dict]:
        """Suggest next actions sorted by priority."""
        ws = self._get_ws(project_id)
        if not ws:
            return []

        recommendations = []

        # 1. Overdue milestones first
        now = datetime.now().isoformat()[:10]
        for m in ws.milestones:
            due = m.get("target_date") or m.get("deadline")
            if due and due < now and m.get("status") != "completed":
                recommendations.append({
                    "priority": 1,
                    "action": "milestone",
                    "title": f"Complete milestone: {m.get('title', 'Untitled')}",
                })

        # 2. Tasks with deadlines coming up
        for t in ws.tasks:
            due = t.get("target_date") or t.get("deadline")
            if due and due >= now and t.get("status") != "done":
                recommendations.append({
                    "priority": 2,
                    "action": "task",
                    "title": f"Task due: {t.get('title', 'Untitled')} ({due})",
                })

        # 3. High-priority open tasks
        for t in ws.tasks:
            prio = t.get("priority", 99)
            if isinstance(prio, str):
                prio = {"high": 1, "medium": 2, "low": 3}.get(prio.lower(), 99)
            if prio <= 2 and t.get("status") != "done":
                recommendations.append({
                    "priority": 3,
                    "action": "task",
                    "title": f"Priority task: {t.get('title', 'Untitled')}",
                })

        # 4. No active goals
        active_goals = [g for g in ws.goals if g.get("status") == "active"]
        if not active_goals:
            recommendations.append({
                "priority": 4,
                "action": "goal",
                "title": "Set active goals for this project",
            })

        # 5. Follow up on recent research
        if ws.research_entries:
            last = ws.research_entries[-1]
            recommendations.append({
                "priority": 5,
                "action": "research",
                "title": f"Follow up on: {last.get('query', 'recent research')}",
            })

        recommendations.sort(key=lambda x: x["priority"])
        return recommendations[:max_items]

    def summarize(self, project_id: str) -> str:
        """Human-readable project summary for LLM context."""
        from datetime import datetime as dt

        ws = self._get_ws(project_id)
        if not ws:
            return ""

        status = self.get_status(project_id)
        lines = [
            f"## Project: {ws.project_name}",
            f"Progress: {status['progress_pct']}% "
            f"({status['completed_tasks']}/{status['total_tasks']} tasks done)",
        ]

        if ws.goals:
            active = [g for g in ws.goals if g.get("status") == "active"]
            lines.append(f"Goals: {len(active)} active / {len(ws.goals)} total")
            for g in active[:3]:
                lines.append(f"  - {g.get('title', 'Untitled')}")

        if ws.milestones:
            upcoming = [
                m for m in ws.milestones if m.get("status") != "completed"
            ]
            if upcoming:
                lines.append("Upcoming milestones:")
                for m in upcoming[:3]:
                    due = m.get("target_date") or m.get("deadline", "no date")
                    lines.append(f"  - {m.get('title', 'Untitled')} (due {due})")

        blockers = self.detect_blockers(project_id)
        if blockers:
            lines.append("Blockers:")
            for b in blockers:
                lines.append(f"  - {b}")

        next_actions = self.recommend_next(project_id, max_items=3)
        if next_actions:
            lines.append("Recommended next:")
            for na in next_actions:
                lines.append(f"  - {na['title']}")

        return "\n".join(lines)

    def _get_ws(self, project_id: str):
        if not self._wm:
            return None
        try:
            return self._wm.get_workspace(project_id)
        except Exception:
            return None
