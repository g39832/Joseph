"""
brain/followup_engine.py
--------------------------
Follow-up recommendation engine for JOSEPH.

Suggests contextually relevant next actions after each response.
Uses simple rule-based matching on recent activity context.

Categories:
- Project: suggest next task or milestone review
- Research: suggest saving sources or adding notes
- Automation: suggest creating a shortcut or scheduling
- General: suggest exploring related topics
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FollowUp:
    text: str
    category: str
    confidence: float
    context: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class FollowUpEngine:
    """
    Generates contextual next-action suggestions.

    Usage:
        engine = FollowUpEngine(project_manager, research_workspace)
        followups = engine.suggest(user_input, response_text)
    """

    def __init__(
        self,
        project_manager=None,
        research_workspace=None,
        activity_tracker=None,
    ):
        self._pm = project_manager
        self._research = research_workspace
        self._tracker = activity_tracker

    def suggest(
        self,
        user_input: str,
        response_text: str,
        max_suggestions: int = 3,
    ) -> list[FollowUp]:
        suggestions = []
        text = f"{user_input} {response_text}".lower()

        # 1. Project-related suggestion
        if self._pm and any(
            kw in text
            for kw in ["project", "goal", "milestone", "task"]
        ):
            try:
                projects = self._pm.project_store.get_active_projects()
                if projects:
                    proj = projects[0]
                    suggestions.append(
                        FollowUp(
                            text=f"Check tasks for '{proj.name}'",
                            category="project",
                            confidence=0.7,
                            context=f"project:{proj.id}",
                        )
                    )
            except Exception:
                pass

        # 2. Research-related suggestion
        if self._research and any(
            kw in text for kw in ["research", "find", "lookup", "search", "source"]
        ):
            suggestions.append(
                FollowUp(
                    text="Save sources or add notes to research workspace",
                    category="research",
                    confidence=0.6,
                )
            )

        # 3. Automation-related suggestion
        if any(
            kw in text
            for kw in ["open", "launch", "run", "automate", "macro"]
        ):
            suggestions.append(
                FollowUp(
                    text="Turn this into an automation shortcut?",
                    category="automation",
                    confidence=0.5,
                )
            )

        # 4. Save or remember
        if any(
            kw in text
            for kw in ["important", "remember", "note", "save", "key"]
        ):
            suggestions.append(
                FollowUp(
                    text="Save this as a note or fact?",
                    category="memory",
                    confidence=0.6,
                )
            )

        # 5. Recent activity tie-in
        if self._tracker:
            recent = self._tracker.recent(5)
            for entry in recent:
                if entry.entry_type == "command" and len(suggestions) < max_suggestions:
                    suggestions.append(
                        FollowUp(
                            text=f"Re-run: {entry.summary[:60]}",
                            category="command",
                            confidence=0.4,
                            context=f"activity:{entry.timestamp}",
                        )
                    )
                    break

        return suggestions[:max_suggestions]

    def suggest_for_context(self, context_type: str) -> list[FollowUp]:
        """Generate suggestions for a specific context (e.g., 'idle')."""
        if context_type == "idle":
            if self._pm:
                try:
                    projects = self._pm.project_store.get_active_projects()
                    if projects:
                        return [
                            FollowUp(
                                text=f"Review progress on '{projects[0].name}'",
                                category="project",
                                confidence=0.5,
                            )
                        ]
                except Exception:
                    pass
        return []
