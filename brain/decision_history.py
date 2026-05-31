"""
brain/decision_history.py
---------------------------
Decision History — tracks major project decisions, design choices,
research conclusions, and important milestones.

Allows users to review why decisions were made and the context
surrounding them.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

DATA_FILE: Path = settings.DATA_DIR / "decision_history.json"


@dataclass
class Decision:
    id: str
    title: str
    description: str
    rationale: str = ""
    alternatives: list[str] = field(default_factory=list)
    outcome: str = ""
    project_id: str = ""
    category: str = "general"  # design | architecture | research | milestone
    tags: list[str] = field(default_factory=list)
    timestamp: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.timestamp


class DecisionHistory:
    """
    Persistent decision log.

    Usage:
        dh = DecisionHistory()
        dh.record(
            title="Switched to qwen2.5:0.5b",
            description="Changed from llama3.1 to smaller model",
            rationale="GPU only has 4GB VRAM",
            category="architecture",
        )
        decisions = dh.get_by_project("proj-123")
    """

    def __init__(self):
        self._decisions: dict[str, Decision] = {}
        self._load()

    def record(
        self,
        title: str,
        description: str,
        rationale: str = "",
        alternatives: list[str] = None,
        outcome: str = "",
        project_id: str = "",
        category: str = "general",
        tags: list[str] = None,
    ) -> Decision:
        decision = Decision(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            rationale=rationale,
            alternatives=alternatives or [],
            outcome=outcome,
            project_id=project_id,
            category=category,
            tags=tags or [],
        )
        self._decisions[decision.id] = decision
        self._save()
        logger.info(f"Decision recorded: {title[:50]}")
        return decision

    def get(self, decision_id: str) -> Optional[Decision]:
        return self._decisions.get(decision_id)

    def get_by_project(self, project_id: str) -> list[Decision]:
        return sorted(
            [d for d in self._decisions.values() if d.project_id == project_id],
            key=lambda d: d.timestamp,
            reverse=True,
        )

    def get_by_category(self, category: str) -> list[Decision]:
        return sorted(
            [d for d in self._decisions.values() if d.category == category],
            key=lambda d: d.timestamp,
            reverse=True,
        )

    def get_all(self) -> list[Decision]:
        return sorted(
            self._decisions.values(),
            key=lambda d: d.timestamp,
            reverse=True,
        )

    def get_recent(self, limit: int = 10) -> list[Decision]:
        return self.get_all()[:limit]

    def search(self, query: str) -> list[Decision]:
        q = query.lower()
        results = []
        for d in self._decisions.values():
            if (
                q in d.title.lower()
                or q in d.description.lower()
                or q in d.rationale.lower()
                or any(q in t.lower() for t in d.tags)
            ):
                results.append(d)
        return sorted(results, key=lambda d: d.timestamp, reverse=True)

    def format_for_context(self, project_id: str, limit: int = 5) -> str:
        """Format decisions for LLM context injection."""
        decisions = self.get_by_project(project_id)[:limit]
        if not decisions:
            return ""
        lines = ["## Decision History"]
        for d in decisions:
            lines.append(f"- {d.title}")
            lines.append(f"  Why: {d.rationale[:100]}" if d.rationale else "")
            if d.alternatives:
                lines.append(f"  Considered: {', '.join(d.alternatives[:3])}")
        return "\n".join(lines)

    def _save(self) -> None:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {did: asdict(d) for did, d in self._decisions.items()}
        with open(str(DATA_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        if not DATA_FILE.exists():
            return
        try:
            with open(str(DATA_FILE), "r", encoding="utf-8") as f:
                data = json.load(f)
            self._decisions = {
                did: Decision(**dfields)
                for did, dfields in data.items()
            }
            logger.info(f"Loaded {len(self._decisions)} decisions")
        except Exception as e:
            logger.warning(f"Failed to load decisions: {e}")
