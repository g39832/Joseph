"""
brain/weekly_review.py
------------------------
Weekly Review System — generates comprehensive weekly summaries
of completed work, active projects, stalled tasks, new research,
knowledge gained, and suggested priorities.

All rule-based — no LLM calls required.
"""

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class WeeklyReview:
    """
    Generates weekly review reports.

    Usage:
        review = WeeklyReview(workspace_manager, project_commander,
                              activity_tracker, insight_engine)
        report = review.generate()
    """

    def __init__(
        self,
        workspace_manager=None,
        project_commander=None,
        activity_tracker=None,
        insight_engine=None,
        research_workspace=None,
        project_store=None,
    ):
        self._wm = workspace_manager
        self._pc = project_commander
        self._tracker = activity_tracker
        self._insights = insight_engine
        self._rw = research_workspace
        self._ps = project_store

    def generate(self) -> str:
        """Generate a full weekly review report."""
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        week_str = week_ago.isoformat()

        sections = [
            f"=== Weekly Review: {now.strftime('%B %d, %Y')} ===\n",
            self._build_completed_section(week_str),
            self._build_active_projects_section(),
            self._build_stalled_section(),
            self._build_research_section(week_str),
            self._build_insights_section(),
            self._build_priorities_section(),
        ]

        return "\n\n".join(s for s in sections if s)

    def _build_completed_section(self, since: str) -> str:
        """Completed tasks and milestones this week."""
        lines = ["Completed This Week:"]

        has_any = False

        if self._ps:
            try:
                for proj in self._ps.get_active_projects():
                    ws = self._wm.get_workspace(proj.id) if self._wm else None
                    if not ws:
                        continue
                    for t in ws.tasks:
                        updated = t.get("updated_at", "")
                        if t.get("status") == "done" and updated >= since:
                            lines.append(
                                f"  Task: {t.get('title', 'Untitled')} "
                                f"(in {proj.name})"
                            )
                            has_any = True
                    for m in ws.milestones:
                        updated = m.get("updated_at", "")
                        if m.get("status") == "completed" and updated >= since:
                            lines.append(
                                f"  Milestone: {m.get('title', 'Untitled')} "
                                f"(in {proj.name})"
                            )
                            has_any = True
            except Exception:
                pass

        if not has_any:
            lines.append("  No tasks or milestones completed this week.")

        return "\n".join(lines)

    def _build_active_projects_section(self) -> str:
        lines = ["Active Projects:"]
        if not self._ps:
            lines.append("  Project system not available.")
            return "\n".join(lines)

        try:
            projects = self._ps.get_active_projects()
            if not projects:
                lines.append("  No active projects.")
                return "\n".join(lines)

            for proj in projects:
                status = (
                    self._pc.get_status(proj.id)
                    if self._pc else {}
                )
                pct = status.get("progress_pct", 0)
                lines.append(
                    f"  {proj.name}: {pct}% complete "
                    f"({status.get('open_tasks', 0)} open tasks)"
                )
        except Exception:
            lines.append("  Error reading projects.")

        return "\n".join(lines)

    def _build_stalled_section(self) -> str:
        lines = ["Stalled / Stuck Items:"]
        has_any = False

        if self._pc and self._ps:
            try:
                for proj in self._ps.get_active_projects():
                    blockers = self._pc.detect_blockers(proj.id)
                    if blockers:
                        has_any = True
                        lines.append(f"  {proj.name}:")
                        for b in blockers[:3]:
                            lines.append(f"    - {b}")
            except Exception:
                pass

        if not has_any:
            lines.append("  Nothing appears stalled.")

        return "\n".join(lines)

    def _build_research_section(self, since: str) -> str:
        lines = ["New Research & Learning:"]
        has_any = False

        if self._rw:
            try:
                for entry in self._rw.get_all():
                    created = entry.created_at
                    if created >= since:
                        has_any = True
                        lines.append(f"  - {entry.query[:80]}")
                        if entry.sources:
                            lines.append(f"    ({len(entry.sources)} sources)")
            except Exception:
                pass

        if not has_any:
            lines.append("  No new research this week.")

        return "\n".join(lines)

    def _build_insights_section(self) -> str:
        lines = ["Knowledge & Insights:"]
        if self._insights:
            try:
                summary = self._insights.get_summary()
                if summary and summary != "No insights yet.":
                    lines.append(f"  {summary}")
                else:
                    lines.append("  Insights not yet available.")
            except Exception:
                lines.append("  Error reading insights.")
        else:
            lines.append("  Insight engine not available.")

        return "\n".join(lines)

    def _build_priorities_section(self) -> str:
        lines = ["Suggested Priorities for Next Week:"]

        if self._pc and self._ps:
            try:
                for proj in self._ps.get_active_projects():
                    recs = self._pc.recommend_next(proj.id, max_items=2)
                    if recs:
                        lines.append(f"  {proj.name}:")
                        for r in recs:
                            lines.append(f"    - {r['title']}")
            except Exception:
                pass

        return "\n".join(lines)

    def generate_short(self) -> str:
        """One-line summary for dashboard."""
        if self._ps:
            try:
                projects = self._ps.get_active_projects()
                total_open = 0
                total_done = 0
                for proj in projects:
                    status = (
                        self._pc.get_status(proj.id)
                        if self._pc else {}
                    )
                    total_open += status.get("open_tasks", 0)
                    total_done += status.get("completed_tasks", 0)
                return (
                    f"Weekly: {len(projects)} active projects, "
                    f"{total_open} open tasks, "
                    f"{total_done} completed"
                )
            except Exception:
                pass
        return ""
