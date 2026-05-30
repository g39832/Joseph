"""
hyper/personality.py
--------------------
Assistant personality engine inspired by high-end assistant behavior.

This module keeps the assistant professional, proactive, and context-aware
without copying any specific copyrighted character or dialogue.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

try:
    from brain.personality_engine import AdvancedPersonality
except Exception:  # pragma: no cover - best effort fallback
    class AdvancedPersonality:  # type: ignore
        def update(self, user_message: str) -> None:
            pass

        def get_system_modifier(self) -> str:
            return ""

        def format_response(self, raw: str) -> str:
            return raw.strip()

        def get_session_summary(self) -> str:
            return ""

try:
    from brain.personality_learning import PersonalityLearning
except Exception:  # pragma: no cover - best effort fallback
    class PersonalityLearning:  # type: ignore
        def get_style_modifier(self) -> str:
            return ""

logger = logging.getLogger(__name__)


class AssistantPersonalityEngine:
    """High-level response style and proactive suggestion coordinator."""

    def __init__(self, memory=None):
        self.memory = memory
        self._advanced = AdvancedPersonality()
        self._learning = PersonalityLearning()
        self._long_term_goals: list[dict] = []
        self._last_user_input = ""

    def update(self, user_input: str) -> None:
        self._last_user_input = user_input
        self._advanced.update(user_input)

    def track_goal(self, goal: str, status: str = "active", priority: int = 2) -> str:
        goal_id = f"goal_{len(self._long_term_goals) + 1}"
        self._long_term_goals.append(
            {
                "id": goal_id,
                "goal": goal,
                "status": status,
                "priority": priority,
                "created_at": datetime.now().isoformat(),
            }
        )
        return goal_id

    def complete_goal(self, goal_id: str) -> bool:
        for goal in self._long_term_goals:
            if goal["id"] == goal_id:
                goal["status"] = "completed"
                goal["completed_at"] = datetime.now().isoformat()
                return True
        return False

    def get_modifier(self, user_input: str = "", memory_context: str = "") -> str:
        """
        Return a concise modifier string for the system prompt.
        """
        parts = []
        if user_input:
            self.update(user_input)

        advanced_modifier = self._advanced.get_system_modifier()
        if advanced_modifier:
            parts.append(advanced_modifier)

        style = self._learning.get_style_modifier()
        if style:
            parts.append(style)

        if self._long_term_goals:
            active = [g["goal"] for g in self._long_term_goals if g["status"] == "active"][:3]
            if active:
                parts.append("Long-term goals: " + "; ".join(active))

        if memory_context:
            parts.append("Use remembered context when relevant.")

        return " ".join(parts)

    def suggest_next_actions(self, user_input: str, memory_context: str = "") -> list[str]:
        """Suggest a few next steps, prioritized by likely user intent."""
        text = f"{user_input} {memory_context}".lower()
        suggestions = []

        if any(word in text for word in ["research", "learn", "compare", "analyze"]):
            suggestions.append("Offer a concise research summary with sources.")
        if any(word in text for word in ["task", "todo", "schedule", "remind"]):
            suggestions.append("Break the request into next actionable steps.")
        if any(word in text for word in ["remember", "preferences", "like", "prefer"]):
            suggestions.append("Store the preference in long-term memory.")
        if any(word in text for word in ["fix", "debug", "error", "issue"]):
            suggestions.append("Propose the smallest safe troubleshooting step first.")

        if not suggestions:
            suggestions.append("Respond directly and keep the answer concise.")
            suggestions.append("Offer one useful next step if appropriate.")

        return suggestions[:3]

    def format_response(self, raw_response: str, detailed: Optional[bool] = None) -> str:
        """Format output using the existing personality engine plus learned style."""
        response = self._advanced.format_response(raw_response)
        if detailed is False:
            return response.split("\n")[0].strip()
        return response

    def get_session_summary(self) -> str:
        return self._advanced.get_session_summary()

    def __repr__(self) -> str:
        return f"AssistantPersonalityEngine(goals={len(self._long_term_goals)})"
