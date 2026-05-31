"""
brain/multimodal_memory.py
----------------------------
Multimodal Memory — allows memories to reference images, documents,
research papers, and screenshots. Links media to projects and memory entries.

Usage:
    mm = MultimodalMemory(memory_manager, research_workspace)
    entry = mm.store_media("path/to/image.png", "screenshot", project_id="...")
    refs = mm.get_media_for_project("proj-123")
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

MEDIA_DIR: Path = settings.DATA_DIR / "media"
DATA_FILE: Path = settings.DATA_DIR / "multimodal_memory.json"


@dataclass
class MediaEntry:
    id: str
    path: str
    media_type: str  # image | document | paper | screenshot
    description: str = ""
    project_id: str = ""
    memory_id: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class MultimodalMemory:
    """
    Stores and retrieves media references linked to memories and projects.

    Media files are copied to data/media/ for persistence.
    References are stored in data/multimodal_memory.json.

    Usage:
        mm = MultimodalMemory()
        entry = mm.store("path/to/image.png", "image", project_id="proj-123")
        entries = mm.get_by_project("proj-123")
    """

    def __init__(self):
        self._entries: dict[str, MediaEntry] = {}
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    def store(
        self,
        source_path: str,
        media_type: str,
        description: str = "",
        project_id: str = "",
        memory_id: str = "",
        tags: list[str] = None,
    ) -> Optional[MediaEntry]:
        """
        Store a media file and create a reference entry.

        The file is copied to data/media/ for persistence.
        """
        if not os.path.exists(source_path):
            logger.warning(f"Media file not found: {source_path}")
            return None

        ext = os.path.splitext(source_path)[1].lower()
        entry_id = str(uuid.uuid4())
        dest_filename = f"{entry_id}{ext}"
        dest_path = MEDIA_DIR / dest_filename

        try:
            import shutil
            shutil.copy2(source_path, str(dest_path))
        except Exception as e:
            logger.warning(f"Failed to copy media: {e}")
            return None

        entry = MediaEntry(
            id=entry_id,
            path=str(dest_path),
            media_type=media_type,
            description=description,
            project_id=project_id,
            memory_id=memory_id,
            tags=tags or [],
        )
        self._entries[entry_id] = entry
        self._save()
        logger.info(f"Media stored: {dest_filename} ({media_type})")
        return entry

    def get(self, entry_id: str) -> Optional[MediaEntry]:
        return self._entries.get(entry_id)

    def get_by_project(self, project_id: str) -> list[MediaEntry]:
        return [
            e for e in self._entries.values()
            if e.project_id == project_id
        ]

    def get_by_type(self, media_type: str) -> list[MediaEntry]:
        return [
            e for e in self._entries.values()
            if e.media_type == media_type
        ]

    def get_by_memory(self, memory_id: str) -> list[MediaEntry]:
        return [
            e for e in self._entries.values()
            if e.memory_id == memory_id
        ]

    def get_all(self) -> list[MediaEntry]:
        return list(self._entries.values())

    def get_recent(self, limit: int = 20) -> list[MediaEntry]:
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: e.created_at,
            reverse=True,
        )
        return sorted_entries[:limit]

    def delete(self, entry_id: str) -> bool:
        entry = self._entries.get(entry_id)
        if not entry:
            return False
        # Delete the file
        try:
            if os.path.exists(entry.path):
                os.remove(entry.path)
        except Exception:
            pass
        del self._entries[entry_id]
        self._save()
        return True

    def link_to_memory(self, entry_id: str, memory_id: str) -> bool:
        entry = self._entries.get(entry_id)
        if not entry:
            return False
        entry.memory_id = memory_id
        entry.updated_at = datetime.now().isoformat()
        self._save()
        return True

    def get_stats(self) -> dict:
        counts = {}
        for e in self._entries.values():
            counts[e.media_type] = counts.get(e.media_type, 0) + 1
        return {
            "total_entries": len(self._entries),
            "by_type": counts,
            "projects_linked": len(
                {e.project_id for e in self._entries.values() if e.project_id}
            ),
        }

    def _save(self) -> None:
        data = {eid: asdict(e) for eid, e in self._entries.items()}
        with open(str(DATA_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        if not DATA_FILE.exists():
            return
        try:
            with open(str(DATA_FILE), "r", encoding="utf-8") as f:
                data = json.load(f)
            self._entries = {
                eid: MediaEntry(**fields)
                for eid, fields in data.items()
            }
            logger.info(f"Loaded {len(self._entries)} media entries")
        except Exception as e:
            logger.warning(f"Failed to load multimodal memory: {e}")
