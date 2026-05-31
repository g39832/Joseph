"""
brain/insight_engine.py
------------------------
Learning insights engine for JOSEPH — now persistent.

Analyzes conversation topics, command usage, and research patterns
to generate periodic "knowledge growth" summaries.

All data persists to disk so insights survive restarts.

Tracks:
- Topics discussed over time
- Skills/commands the user has learned
- Knowledge domains explored
- Frequency of interaction patterns
"""

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

DATA_FILE: Path = settings.DATA_DIR / "insight_history.json"


@dataclass
class Insight:
    category: str
    title: str
    detail: str
    confidence: float = 1.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


TOPIC_KEYWORDS = {
    "programming": [
        "python", "code", "function", "class", "api", "bug", "debug",
        "git", "github", "deploy", "server", "database", "sql", "docker",
    ],
    "automation": [
        "automate", "macro", "shortcut", "schedule", "cron", "task",
        "workflow", "pipeline", "batch", "script",
    ],
    "research": [
        "research", "paper", "article", "study", "source", "citation",
        "reference", "find", "search", "lookup",
    ],
    "productivity": [
        "project", "goal", "milestone", "task", "deadline", "plan",
        "organize", "track", "progress", "status",
    ],
    "system": [
        "system", "settings", "config", "update", "install", "memory",
        "performance", "cpu", "gpu", "disk",
    ],
}


class InsightEngine:
    """
    Analyzes activity and generates knowledge insights — persistent.

    Usage:
        engine = InsightEngine(activity_tracker)
        topics = engine.get_topic_breakdown()
        insights = engine.generate_insights()
    """

    def __init__(self, activity_tracker=None):
        self._tracker = activity_tracker
        self._topic_counts: Counter = Counter()
        self._command_counts: Counter = Counter()
        self._session_start = datetime.now()
        self._last_insight_time = 0.0
        self._insight_cooldown = 3600
        self._insights: list[Insight] = []
        self._load()

    def _save(self) -> None:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "topic_counts": dict(self._topic_counts),
            "command_counts": dict(self._command_counts),
            "insights": [
                {**asdict(i)}
                for i in self._insights
            ],
            "last_insight_time": self._last_insight_time,
        }
        with open(str(DATA_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        if not DATA_FILE.exists():
            return
        try:
            with open(str(DATA_FILE), "r", encoding="utf-8") as f:
                data = json.load(f)
            self._topic_counts = Counter(data.get("topic_counts", {}))
            self._command_counts = Counter(data.get("command_counts", {}))
            raw_insights = data.get("insights", [])
            self._insights = [Insight(**i) for i in raw_insights]
            self._last_insight_time = data.get("last_insight_time", 0.0)
            logger.info(
                f"Loaded {len(self._insights)} insights, "
                f"{len(self._topic_counts)} topics, "
                f"{len(self._command_counts)} commands"
            )
        except Exception as e:
            logger.warning(f"Failed to load insights: {e}")

    def ingest(self, entry) -> None:
        if not entry:
            return

        if entry.entry_type == "command":
            self._command_counts[entry.summary] += 1

        text = f"{entry.summary} {entry.detail}".lower()
        for topic, keywords in TOPIC_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    self._topic_counts[topic] += 1
                    break

        now = time.time()
        if (
            now - self._last_insight_time > self._insight_cooldown
            and len(self._topic_counts) >= 2
        ):
            self._generate_insights()
            self._last_insight_time = now
            self._save()

    def _generate_insights(self) -> None:
        new_insights = []

        if self._topic_counts:
            top_topic = self._topic_counts.most_common(1)[0]
            new_insights.append(
                Insight(
                    category="topic",
                    title=f"Primary Focus: {top_topic[0].title()}",
                    detail=f"Your most discussed topic is "
                    f"'{top_topic[0]}' ({top_topic[1]} mentions).",
                    confidence=0.8,
                )
            )

        if self._command_counts:
            top_cmd = self._command_counts.most_common(1)[0]
            new_insights.append(
                Insight(
                    category="usage",
                    title=f"Most Used: {top_cmd[0][:40]}",
                    detail=f"You've used '{top_cmd[0][:60]}' "
                    f"{top_cmd[1]} times.",
                    confidence=0.9,
                )
            )

        if len(self._topic_counts) >= 3:
            new_insights.append(
                Insight(
                    category="diversity",
                    title=f"Exploring {len(self._topic_counts)} Domains",
                    detail=f"You're active across "
                    f"{len(self._topic_counts)} knowledge domains: "
                    f"{', '.join(self._topic_counts.keys())}.",
                    confidence=0.7,
                )
            )

        self._insights = (self._insights + new_insights)[-20:]

    def generate_insights(self) -> list[Insight]:
        self._generate_insights()
        self._save()
        return self._insights

    def get_insights(self, category: Optional[str] = None) -> list[Insight]:
        if category:
            return [i for i in self._insights if i.category == category]
        return self._insights

    def get_topic_breakdown(self) -> dict:
        return dict(self._topic_counts.most_common())

    def get_summary(self) -> str:
        lines = []
        if self._topic_counts:
            lines.append("Topics explored:")
            for topic, count in self._topic_counts.most_common(5):
                lines.append(f"  - {topic}: {count} mentions")
        if self._command_counts:
            lines.append("Commands used:")
            for cmd, count in self._command_counts.most_common(5):
                lines.append(f"  - '{cmd[:50]}': {count}x")
        if not lines:
            return "No insights yet."
        return "\n".join(lines)
