"""
brain/research_workspace.py
----------------------------
Enhanced research workspace for JOSEPH.

Extends the existing research_tracker with source management,
citation tracking, and research-project linking.

Features:
- Save sources with citations (URL, title, snippet)
- Link research entries to projects
- Search across all research notes
- Generate citation lists
- Track research sessions
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

DATA_FILE: Path = settings.DATA_DIR / "research_workspace.json"


@dataclass
class Source:
    url: str = ""
    title: str = ""
    snippet: str = ""
    retrieved_at: str = ""

    def __post_init__(self):
        if not self.retrieved_at:
            self.retrieved_at = datetime.now().isoformat()


@dataclass
class ResearchEntry:
    id: str
    query: str
    notes: str = ""
    project_id: str = ""
    sources: list[Source] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class ResearchWorkspace:
    """
    Structured research workspace with source management.

    Usage:
        ws = ResearchWorkspace()
        entry = ws.add_entry("quantum computing", notes="...")
        ws.add_source(entry.id, url="https://...", title="Paper")
    """

    def __init__(self):
        self._entries: dict[str, ResearchEntry] = {}
        self._load()

    def add_entry(
        self,
        query: str,
        notes: str = "",
        project_id: str = "",
        tags: list[str] = None,
    ) -> ResearchEntry:
        import uuid
        entry = ResearchEntry(
            id=str(uuid.uuid4()),
            query=query,
            notes=notes,
            project_id=project_id,
            tags=tags or [],
        )
        self._entries[entry.id] = entry
        self._save()
        logger.info(f"Research entry added: {query[:50]}")
        return entry

    def update_entry(self, entry_id: str, **kwargs) -> None:
        entry = self._entries.get(entry_id)
        if not entry:
            return
        allowed = {"notes", "project_id", "tags", "query"}
        for k, v in kwargs.items():
            if k in allowed:
                setattr(entry, k, v)
        entry.updated_at = datetime.now().isoformat()
        self._save()

    def add_source(
        self,
        entry_id: str,
        url: str,
        title: str = "",
        snippet: str = "",
    ) -> bool:
        entry = self._entries.get(entry_id)
        if not entry:
            return False
        entry.sources.append(
            Source(url=url, title=title, snippet=snippet)
        )
        entry.updated_at = datetime.now().isoformat()
        self._save()
        return True

    def get_entry(self, entry_id: str) -> Optional[ResearchEntry]:
        return self._entries.get(entry_id)

    def get_all(self) -> list[ResearchEntry]:
        return list(self._entries.values())

    def search(self, query: str) -> list[ResearchEntry]:
        q = query.lower()
        results = []
        for entry in self._entries.values():
            if (
                q in entry.query.lower()
                or q in entry.notes.lower()
                or any(q in t.lower() for t in entry.tags)
                or any(q in s.title.lower() for s in entry.sources)
            ):
                results.append(entry)
        return results

    def get_by_project(self, project_id: str) -> list[ResearchEntry]:
        return [
            e
            for e in self._entries.values()
            if e.project_id == project_id
        ]

    def get_citations(self, entry_id: str) -> list[str]:
        entry = self._entries.get(entry_id)
        if not entry or not entry.sources:
            return []
        citations = []
        for i, src in enumerate(entry.sources, 1):
            title = src.title or "Untitled"
            url = src.url or ""
            citations.append(f"[{i}] {title}. {url}")
        return citations

    def get_all_citations(self) -> list[str]:
        all_citations = []
        for entry in self._entries.values():
            for src in entry.sources:
                title = src.title or "Untitled"
                url = src.url or ""
                all_citations.append(f"'{entry.query}': {title}. {url}")
        return all_citations

    def delete_entry(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._save()
            return True
        return False

    def get_stats(self) -> dict:
        total_sources = sum(
            len(e.sources) for e in self._entries.values()
        )
        return {
            "total_entries": len(self._entries),
            "total_sources": total_sources,
            "projects_linked": len(
                {e.project_id for e in self._entries.values() if e.project_id}
            ),
        }

    def _save(self) -> None:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            eid: asdict(e)
            for eid, e in self._entries.items()
        }
        with open(str(DATA_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        if not DATA_FILE.exists():
            self._entries = {}
            return
        try:
            with open(str(DATA_FILE), "r", encoding="utf-8") as f:
                data = json.load(f)
            self._entries = {}
            for eid, fields in data.items():
                fields["sources"] = [
                    Source(**s) for s in fields.get("sources", [])
                ]
                self._entries[eid] = ResearchEntry(**fields)
            logger.info(
                f"Loaded {len(self._entries)} research entries"
            )
        except Exception as e:
            logger.warning(f"Failed to load research workspace: {e}")
            self._entries = {}
