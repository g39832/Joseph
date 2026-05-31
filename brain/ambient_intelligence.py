"""
brain/ambient_intelligence.py
-------------------------------
Ambient intelligence for JOSEPH.

Detects patterns in user behavior and generates non-intrusive
suggestions. Runs in the background (triggered by ActivityTracker
events) and surfaces insights when relevant.

Features:
- Detect unfinished tasks or stalled goals
- Identify repeated commands/suggest shortcut creation
- Notice usage patterns (e.g., user always asks for weather at 8am)
- Suggest follow-ups based on recent activity
"""

import logging
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AmbientSuggestion:
    suggestion_type: str
    message: str
    confidence: float
    source: str = "ambient"
    timestamp: str = ""
    dismissed: bool = False

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class AmbientIntelligence:
    """
    Background pattern detector and suggestion generator.

    Usage:
        ai = AmbientIntelligence()
        ai.ingest(activity_entry)
        suggestions = ai.get_suggestions()
    """

    def __init__(self, activity_tracker=None, project_manager=None):
        self._tracker = activity_tracker
        self._pm = project_manager
        self._suggestions: list[AmbientSuggestion] = []
        self._max_suggestions = 10
        self._seen_commands: Counter = Counter()
        self._last_suggestion_time = 0.0
        self._suggestion_cooldown = 300  # 5 min between suggestions
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        logger.info(f"Ambient intelligence {'enabled' if value else 'disabled'}")

    def set_tracker(self, tracker) -> None:
        self._tracker = tracker

    def ingest(self, entry) -> None:
        if not self._enabled:
            return

        if entry.entry_type == "command":
            self._seen_commands[entry.summary] += 1

        # Generate suggestions periodically
        now = time.time()
        if (
            now - self._last_suggestion_time > self._suggestion_cooldown
            and self._tracker
        ):
            self._generate_suggestions()
            self._last_suggestion_time = now

    def _generate_suggestions(self) -> None:
        """Analyze recent activity and produce suggestions."""
        if not self._tracker:
            return

        recent = self._tracker.recent(50)
        if not recent:
            return

        new_suggestions = []

        # 1. Detect repeated commands
        for cmd, count in self._seen_commands.most_common(3):
            if count >= 3:
                new_suggestions.append(
                    AmbientSuggestion(
                        suggestion_type="shortcut",
                        message=f"You've run '{cmd}' {count} times. "
                        f"Want me to create a shortcut?",
                        confidence=min(0.5 + count * 0.1, 0.9),
                    )
                )

        # 2. Stalled projects
        if self._pm:
            try:
                projects = self._pm.project_store.get_active_projects()
                for proj in projects:
                    goals = self._pm.goal_tracker.get_goals(
                        project_id=proj.id
                    )
                    if goals:
                        stalled = [
                            g
                            for g in goals
                            if g.status == "active"
                            and g.target_date
                        ]
                        if stalled:
                            new_suggestions.append(
                                AmbientSuggestion(
                                    suggestion_type="stalled_goal",
                                    message=f"Project '{proj.name}' has "
                                    f"{len(stalled)} goal(s) with deadlines. "
                                    f"Review progress?",
                                    confidence=0.6,
                                )
                            )
            except Exception:
                pass

        # 3. Usage pattern detection from timestamps
        hourly = Counter()
        for entry in recent:
            try:
                hour = int(entry.timestamp[11:13])
                hourly[hour] += 1
            except Exception:
                pass
        if hourly:
            peak_hour = hourly.most_common(1)[0]
            current_hour = datetime.now().hour
            if peak_hour[0] == current_hour and peak_hour[1] >= 10:
                new_suggestions.append(
                    AmbientSuggestion(
                        suggestion_type="peak_usage",
                        message=f"You're most active around "
                        f"{peak_hour[0]:02d}:00. "
                        f"Anything I can prepare in advance?",
                        confidence=0.4,
                    )
                )

        # Merge: keep existing undismissed, add new, limit
        old = [s for s in self._suggestions if not s.dismissed]
        self._suggestions = (old + new_suggestions)[: self._max_suggestions]

    def get_suggestions(self, min_confidence: float = 0.0) -> list[AmbientSuggestion]:
        return [
            s
            for s in self._suggestions
            if not s.dismissed and s.confidence >= min_confidence
        ]

    def dismiss(self, index: int) -> bool:
        if 0 <= index < len(self._suggestions):
            self._suggestions[index].dismissed = True
            return True
        return False

    def clear(self) -> None:
        self._suggestions.clear()
        self._seen_commands.clear()
