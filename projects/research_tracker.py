"""
projects/research_tracker.py
----------------------------
Research note tracking for JOSEPH projects.

Stores research findings, URLs, and notes associated with a project.
Supports full-text search and recency-based retrieval.
"""

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from projects.project_store import _read_json, _write_json
from configs.settings import settings

logger = logging.getLogger(__name__)

_DATA_FILE = settings.DATA_DIR / "projects.json"
_STORAGE_KEY = "research_notes"


@dataclass
class ResearchNote:
    """A research finding or note associated with a project."""
    id: str
    project_id: str
    title: str
    content: str
    url: Optional[str] = None
    source: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    relevance: int = 3  # 1-5 scale


def _now() -> str:
    return datetime.now().isoformat()


class ResearchTracker:
    """
    Manages research notes within projects.

    Usage:
        rt = ResearchTracker()
        note = rt.add_note(project_id, "LLM Paper Summary", content="...", url="...")
        results = rt.search_notes("transformer")
    """

    def __init__(self):
        self._notes: dict[str, ResearchNote] = {}
        self.load()

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def add_note(
        self,
        project_id: str,
        title: str,
        content: str,
        url: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[list[str]] = None,
        relevance: int = 3,
    ) -> ResearchNote:
        """
        Add a research note to a project.

        Args:
            project_id: The owning project's ID.
            title: Note title.
            content: Note body / findings.
            url: Optional reference URL.
            source: Optional source name (e.g. "ArXiv", "manual").
            tags: Optional list of tag strings.
            relevance: Importance rating 1-5 (default 3).

        Returns:
            The newly created ResearchNote.
        """
        note = ResearchNote(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title=title,
            content=content,
            url=url,
            source=source or "",
            tags=tags or [],
            relevance=relevance,
            created_at=_now(),
        )
        self._notes[note.id] = note
        self.save()
        logger.info(f"Research note added: {note.title} ({note.id[:8]}...)")
        return note

    def get_notes(self, project_id: str) -> list[ResearchNote]:
        """Get all research notes for a project, newest first."""
        notes = [
            n for n in self._notes.values()
            if n.project_id == project_id
        ]
        return sorted(notes, key=lambda n: n.created_at or "", reverse=True)

    def get_note(self, note_id: str) -> Optional[ResearchNote]:
        """Retrieve a single research note by ID."""
        return self._notes.get(note_id)

    def delete_note(self, note_id: str) -> bool:
        """Delete a research note by ID. Returns True if deleted."""
        if note_id in self._notes:
            del self._notes[note_id]
            self.save()
            logger.info(f"Research note deleted: {note_id[:8]}...")
            return True
        return False

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def search_notes(self, query: str, project_id: Optional[str] = None) -> list[ResearchNote]:
        """
        Search research notes by title, content, source, or tags.

        Args:
            query: Case-insensitive search string.
            project_id: If provided, scope search to this project.

        Returns:
            Matching ResearchNotes, ordered by relevance then recency.
        """
        q = query.lower()
        results = []
        for note in self._notes.values():
            if project_id and note.project_id != project_id:
                continue
            if (
                q in note.title.lower()
                or q in note.content.lower()
                or q in note.source.lower()
                or any(q in t.lower() for t in note.tags)
            ):
                results.append(note)

        results.sort(key=lambda n: (-n.relevance, n.created_at or ""), reverse=False)
        return results

    def get_recent_notes(self, limit: int = 10) -> list[ResearchNote]:
        """Return the most recently created research notes across all projects."""
        sorted_notes = sorted(
            self._notes.values(),
            key=lambda n: n.created_at or "",
            reverse=True,
        )
        return sorted_notes[:limit]

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        """Persist research notes to the shared JSON data file."""
        all_data = _read_json(_DATA_FILE)
        all_data[_STORAGE_KEY] = {
            nid: asdict(n) for nid, n in self._notes.items()
        }
        _write_json(_DATA_FILE, all_data)
        logger.debug(f"Saved {len(self._notes)} research notes")

    def load(self) -> None:
        """Load research notes from the shared JSON data file."""
        if not _DATA_FILE.exists():
            self._notes = {}
            return

        try:
            all_data = _read_json(_DATA_FILE)
            raw = all_data.get(_STORAGE_KEY, {})
            self._notes = {}
            for nid, fields in raw.items():
                try:
                    self._notes[nid] = ResearchNote(**fields)
                except Exception as e:
                    logger.warning(f"Skipping malformed research note {nid}: {e}")
            logger.info(f"Loaded {len(self._notes)} research notes")
        except Exception as e:
            logger.warning(f"Failed to load research notes: {e}")
            self._notes = {}
