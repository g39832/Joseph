"""
brain/learning_companion.py
-----------------------------
Learning Companion Mode — tracks learning goals, completed topics,
recommends next topics, builds study plans, and creates review schedules.

Integrates with project system, roadmap engine, and memory.
Rule-based — no LLM calls.
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

DATA_FILE: Path = settings.DATA_DIR / "learning_companion.json"


@dataclass
class LearningGoal:
    id: str
    topic: str
    category: str = ""
    target_level: str = "intermediate"
    completed_topics: list[str] = field(default_factory=list)
    current_topic: str = ""
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class StudySession:
    id: str
    topic: str
    goal_id: str
    duration_minutes: int = 0
    notes: str = ""
    date: str = ""

    def __post_init__(self):
        if not self.date:
            self.date = datetime.now().isoformat()[:10]


@dataclass
class ReviewSchedule:
    goal_id: str
    topic: str
    next_review: str
    interval_days: int = 1
    last_reviewed: str = ""


# Spaced repetition intervals (days)
REVIEW_INTERVALS = [1, 3, 7, 14, 30, 90]


class LearningCompanion:
    """
    Tracks learning goals, topics, study sessions, and review schedules.

    Usage:
        lc = LearningCompanion(roadmap_engine)
        goal = lc.create_goal("Rust", category="programming")
        lc.complete_topic(goal.id, "Rust Fundamentals")
        lc.log_study_session(goal.id, "Rust Fundamentals", 45)
        recs = lc.recommend_next_topic(goal.id)
    """

    def __init__(self, roadmap_engine=None, workspace_manager=None):
        self._rm = roadmap_engine
        self._wm = workspace_manager
        self._goals: dict[str, LearningGoal] = {}
        self._sessions: list[StudySession] = []
        self._reviews: list[ReviewSchedule] = []
        self._load()

    def create_goal(
        self, topic: str, category: str = "",
        target_level: str = "intermediate",
    ) -> LearningGoal:
        import uuid
        goal = LearningGoal(
            id=str(uuid.uuid4()),
            topic=topic,
            category=category,
            target_level=target_level,
        )
        self._goals[goal.id] = goal
        self._save()
        logger.info(f"Learning goal created: {topic}")
        return goal

    def complete_topic(self, goal_id: str, topic: str) -> bool:
        goal = self._goals.get(goal_id)
        if not goal:
            return False
        if topic not in goal.completed_topics:
            goal.completed_topics.append(topic)
        goal.updated_at = datetime.now().isoformat()

        # Set up review schedule
        self._reviews.append(ReviewSchedule(
            goal_id=goal_id,
            topic=topic,
            next_review=(datetime.now() + timedelta(days=1)).isoformat()[:10],
            interval_days=1,
            last_reviewed=datetime.now().isoformat()[:10],
        ))

        self._save()
        return True

    def log_study_session(
        self, goal_id: str, topic: str, duration_minutes: int,
        notes: str = "",
    ) -> StudySession:
        import uuid
        session = StudySession(
            id=str(uuid.uuid4()),
            topic=topic,
            goal_id=goal_id,
            duration_minutes=duration_minutes,
            notes=notes,
        )
        self._sessions.append(session)
        self._save()
        return session

    def recommend_next_topic(self, goal_id: str) -> list[str]:
        goal = self._goals.get(goal_id)
        if not goal:
            return []

        completed = set(goal.completed_topics)
        suggestions = []

        if self._rm:
            remaining = self._rm.suggest_next_topics(list(completed))
            if remaining:
                suggestions.extend(remaining)

        # If roadmap says nothing, suggest reviewing completed topics
        if not suggestions and completed:
            suggestions.append(f"Review {list(completed)[-1]}")

        return suggestions

    def get_due_reviews(self) -> list[ReviewSchedule]:
        today = datetime.now().isoformat()[:10]
        return [
            r for r in self._reviews
            if r.next_review <= today
        ]

    def complete_review(self, goal_id: str, topic: str) -> bool:
        for r in self._reviews:
            if r.goal_id == goal_id and r.topic == topic:
                idx = REVIEW_INTERVALS.index(r.interval_days) if r.interval_days in REVIEW_INTERVALS else -1
                next_interval = REVIEW_INTERVALS[idx + 1] if idx + 1 < len(REVIEW_INTERVALS) else REVIEW_INTERVALS[-1]
                r.interval_days = next_interval
                r.last_reviewed = datetime.now().isoformat()[:10]
                r.next_review = (
                    datetime.now() + timedelta(days=next_interval)
                ).isoformat()[:10]
                self._save()
                return True
        return False

    def get_goals(self, status: str = "active") -> list[LearningGoal]:
        return [g for g in self._goals.values() if g.status == status]

    def get_all_goals(self) -> list[LearningGoal]:
        return list(self._goals.values())

    def get_study_stats(self) -> dict:
        total_minutes = sum(s.duration_minutes for s in self._sessions)
        total_sessions = len(self._sessions)
        return {
            "total_sessions": total_sessions,
            "total_hours": round(total_minutes / 60, 1),
            "active_goals": len([g for g in self._goals.values() if g.status == "active"]),
            "completed_topics": sum(
                len(g.completed_topics) for g in self._goals.values()
            ),
        }

    def get_summary(self) -> str:
        stats = self.get_study_stats()
        lines = [
            "Learning Companion:",
            f"  Goals: {stats['active_goals']} active",
            f"  Sessions: {stats['total_sessions']} ({stats['total_hours']}h)",
            f"  Topics completed: {stats['completed_topics']}",
        ]
        due = self.get_due_reviews()
        if due:
            lines.append(f"  Reviews due: {len(due)}")
            for r in due[:3]:
                lines.append(f"    - {r.topic}")
        return "\n".join(lines)

    def _save(self) -> None:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "goals": {gid: asdict(g) for gid, g in self._goals.items()},
            "sessions": [asdict(s) for s in self._sessions],
            "reviews": [asdict(r) for r in self._reviews],
        }
        with open(str(DATA_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        if not DATA_FILE.exists():
            return
        try:
            with open(str(DATA_FILE), "r", encoding="utf-8") as f:
                data = json.load(f)
            self._goals = {
                gid: LearningGoal(**gdata)
                for gid, gdata in data.get("goals", {}).items()
            }
            self._sessions = [
                StudySession(**s) for s in data.get("sessions", [])
            ]
            self._reviews = [
                ReviewSchedule(**r) for r in data.get("reviews", [])
            ]
        except Exception as e:
            logger.warning(f"Failed to load learning data: {e}")
