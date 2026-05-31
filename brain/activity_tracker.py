"""
brain/activity_tracker.py
--------------------------
Activity & decision log for JOSEPH — now persistent.

Records every action, tool use, decision, and memory retrieval
so Joseph can explain why things happened and provide transparency.

All data persists to disk so nothing is lost between restarts.

Tracks:
- User messages and assistant responses
- Tools invoked and why
- Memory retrievals and their relevance
- Decisions made by agents
- Automation commands executed
- Timing for each action
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

MAX_ENTRIES = 500
DATA_FILE: Path = settings.DATA_DIR / "activity_history.json"


@dataclass
class ActivityEntry:
    entry_type: str
    summary: str
    detail: str = ""
    category: str = "general"
    duration_ms: float = 0.0
    source: str = "system"
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class ActivityTracker:
    """
    Persistent ring-buffer activity log.

    Usage:
        tracker = ActivityTracker()
        tracker.log("tool", "Opened Chrome", category="automation", duration_ms=1200)
        entries = tracker.recent(10)
        filtered = tracker.filter(category="automation")
    """

    def __init__(self, max_entries: int = MAX_ENTRIES):
        self._entries: list[ActivityEntry] = []
        self._max = max_entries
        self._load()

    def _save(self) -> None:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(e) for e in self._entries]
        with open(str(DATA_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        if not DATA_FILE.exists():
            return
        try:
            with open(str(DATA_FILE), "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._entries = [ActivityEntry(**e) for e in raw[-self._max:]]
            logger.info(f"Loaded {len(self._entries)} activity entries from disk")
        except Exception as e:
            logger.warning(f"Failed to load activity history: {e}")

    def log(
        self,
        entry_type: str,
        summary: str,
        detail: str = "",
        category: str = "general",
        duration_ms: float = 0.0,
        source: str = "system",
    ) -> None:
        entry = ActivityEntry(
            entry_type=entry_type,
            summary=summary,
            detail=detail,
            category=category,
            duration_ms=duration_ms,
            source=source,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max:
            self._entries.pop(0)
        self._save()

    def recent(self, n: int = 10) -> list[ActivityEntry]:
        return self._entries[-n:]

    def filter(
        self,
        category: Optional[str] = None,
        entry_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 50,
    ) -> list[ActivityEntry]:
        results = self._entries
        if category:
            results = [e for e in results if e.category == category]
        if entry_type:
            results = [e for e in results if e.entry_type == entry_type]
        if source:
            results = [e for e in results if e.source == source]
        return results[-limit:]

    def get_stats(self) -> dict:
        categories = {}
        types = {}
        for e in self._entries[-200:]:
            categories[e.category] = categories.get(e.category, 0) + 1
            types[e.entry_type] = types.get(e.entry_type, 0) + 1
        return {
            "total_entries": len(self._entries),
            "categories": categories,
            "types": types,
            "last_entry": self._entries[-1].summary if self._entries else "",
        }

    def summary(self, n: int = 5) -> str:
        lines = []
        for e in self._entries[-n:]:
            lines.append(
                f"[{e.timestamp[11:19]}] {e.entry_type}: {e.summary} "
                f"({e.duration_ms:.0f}ms)"
            )
        return "\n".join(lines)

    def clear(self) -> None:
        self._entries.clear()
        self._save()
