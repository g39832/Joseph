"""
brain/briefing_v2.py
----------------------
Daily Briefing 2.0 — upgrades the original briefing system with
active projects, today's priorities, upcoming milestones,
research reminders, suggested actions, and system health.

Rule-based — no LLM calls.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class BriefingV2:
    """
    Enhanced daily briefing — command center style.

    Usage:
        briefing = BriefingV2(workspace_manager, project_commander,
                              weekly_review, project_store, ...)
        report = briefing.generate()
    """

    def __init__(
        self,
        workspace_manager=None,
        project_commander=None,
        weekly_review=None,
        project_store=None,
        activity_tracker=None,
        insight_engine=None,
        research_workspace=None,
        weather_service=None,
        scheduler=None,
        notes_manager=None,
        memory_manager=None,
    ):
        self._wm = workspace_manager
        self._pc = project_commander
        self._wr = weekly_review
        self._ps = project_store
        self._tracker = activity_tracker
        self._insights = insight_engine
        self._rw = research_workspace
        self._weather = weather_service
        self._scheduler = scheduler
        self._nm = notes_manager
        self._memory = memory_manager

    def generate(self) -> str:
        """Generate a full command-center briefing."""
        now = datetime.now()
        today = now.strftime("%A, %B %d, %Y")

        sections = [
            f"\u2500" * 50,
            f"  DAILY BRIEFING — {today}",
            f"\u2500" * 50,
            "",
            self._build_system_health(),
            self._build_active_projects(),
            self._build_todays_priorities(),
            self._build_upcoming_milestones(),
            self._build_research_reminders(),
            self._build_suggested_actions(),
            self._build_weather() if self._weather else "",
            self._build_schedule() if self._scheduler else "",
            "",
            f"\u2500" * 50,
            f"  End of Briefing",
            f"\u2500" * 50,
        ]

        return "\n\n".join(s for s in sections if s)

    def _build_system_health(self) -> str:
        lines = ["SYSTEM STATUS"]

        if self._tracker:
            try:
                stats = self._tracker.get_stats()
                entries_today = sum(
                    1 for e in self._tracker._entries
                    if e.timestamp[:10] == datetime.now().isoformat()[:10]
                ) if hasattr(self._tracker, "_entries") else 0
                lines.append(f"  Activities today: {entries_today}")
                lines.append(f"  Total tracked: {stats.get('total_entries', 0)}")
            except Exception:
                pass

        if self._memory:
            try:
                lines.append(f"  Memory: {self._memory.format_status()}")
            except Exception:
                pass

        return "\n".join(lines)

    def _build_active_projects(self) -> str:
        lines = ["ACTIVE PROJECTS"]
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
                    self._pc.get_status(proj.id) if self._pc else {}
                )
                pct = status.get("progress_pct", 0)
                open_t = status.get("open_tasks", 0)
                bar = self._progress_bar(pct)
                lines.append(f"  {proj.name}")
                lines.append(f"    {bar} {pct}% — {open_t} open tasks")
        except Exception as e:
            lines.append(f"  Error: {e}")

        return "\n".join(lines)

    def _build_todays_priorities(self) -> str:
        lines = ["TODAY'S PRIORITIES"]
        has_any = False

        if self._pc and self._ps:
            try:
                for proj in self._ps.get_active_projects():
                    recs = self._pc.recommend_next(proj.id, max_items=2)
                    if recs:
                        has_any = True
                        lines.append(f"  {proj.name}:")
                        for r in recs:
                            lines.append(f"    \u25b6 {r['title']}")
            except Exception:
                pass

        if not has_any:
            lines.append("  No urgent priorities. Check project goals.")

        return "\n".join(lines)

    def _build_upcoming_milestones(self) -> str:
        lines = ["UPCOMING MILESTONES"]
        has_any = False

        now = datetime.now()
        week_from_now = (now + timedelta(days=7)).isoformat()[:10]

        if self._ps:
            try:
                for proj in self._ps.get_active_projects():
                    ws = (
                        self._wm.get_workspace(proj.id)
                        if self._wm else None
                    )
                    if not ws:
                        continue
                    for m in ws.milestones:
                        due = m.get("target_date") or m.get("deadline")
                        if due and due <= week_from_now and m.get("status") != "completed":
                            has_any = True
                            days_left = (datetime.fromisoformat(due) - now).days
                            lines.append(
                                f"  {m.get('title', 'Untitled')} "
                                f"({proj.name}) — {days_left}d remaining"
                            )
            except Exception:
                pass

        if not has_any:
            lines.append("  No milestones due in the next 7 days.")

        return "\n".join(lines)

    def _build_research_reminders(self) -> str:
        lines = ["RESEARCH REMINDERS"]
        has_any = False

        if self._rw:
            try:
                entries = self._rw.get_all()
                if entries:
                    for entry in entries[-3:]:
                        has_any = True
                        src_count = len(entry.sources)
                        lines.append(
                            f"  \U0001F50D {entry.query[:70]} "
                            f"({src_count} sources)"
                        )
            except Exception:
                pass

        if not has_any:
            lines.append("  No research entries.")

        return "\n".join(lines)

    def _build_suggested_actions(self) -> str:
        lines = ["SUGGESTED ACTIONS"]

        if self._wr:
            try:
                priorities = self._wr._build_priorities_section()
                if priorities:
                    lines.append(f"  {priorities}")
            except Exception:
                pass

        if self._insights:
            try:
                topics = self._insights.get_topic_breakdown()
                if topics:
                    top = list(topics.keys())[0]
                    lines.append(f"  \U0001F4DA Continue exploring: {top}")
            except Exception:
                pass

        return "\n".join(lines)

    def _build_weather(self) -> str:
        try:
            w = self._weather.get_weather()
            if w:
                return (
                    f"WEATHER\n"
                    f"  {w.get('temp_f', '?')}F, {w.get('condition', '?')} "
                    f"in {w.get('city', 'your area')}"
                )
        except Exception:
            pass
        return ""

    def _build_schedule(self) -> str:
        try:
            events = self._scheduler.get_upcoming(limit=3)
            if events:
                lines = ["TODAY'S SCHEDULE"]
                for e in events:
                    lines.append(f"  \u23f0 {e.get('title', 'Event')}")
                return "\n".join(lines)
        except Exception:
            pass
        return ""

    @staticmethod
    def _progress_bar(pct: int, width: int = 16) -> str:
        filled = int((pct / 100) * width)
        return "\u2588" * filled + "\u2591" * (width - filled)
