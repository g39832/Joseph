"""
brain/research_pipeline.py
----------------------------
Research Pipelines — allows research to evolve over time with
threads, notes, sources, citations, summaries, linked projects,
and follow-up questions.

Extends the existing ResearchWorkspace with threaded research.
"""

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ResearchNote:
    content: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class FollowUp:
    question: str
    answered: bool = False
    answer: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ResearchThread:
    id: str
    topic: str
    summary: str = ""
    notes: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    follow_ups: list[dict] = field(default_factory=list)
    project_id: str = ""
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class ResearchPipeline:
    """
    Threaded research that evolves over time.

    Usage:
        rp = ResearchPipeline()
        thread = rp.create_thread("Quantum computing", project_id="...")
        rp.add_note(thread.id, "Found a promising paper")
        rp.add_follow_up(thread.id, "What is Shor's algorithm?")
        rp.answer_follow_up(thread.id, follow_up_id, "It factors primes...")
    """

    def __init__(self, research_workspace=None):
        self._rw = research_workspace
        self._threads: dict[str, ResearchThread] = {}

    def create_thread(
        self, topic: str, project_id: str = "",
        summary: str = "",
    ) -> ResearchThread:
        thread = ResearchThread(
            id=str(uuid.uuid4()),
            topic=topic,
            summary=summary,
            project_id=project_id,
        )
        self._threads[thread.id] = thread
        logger.info(f"Research thread created: {topic[:50]}")
        return thread

    def add_note(self, thread_id: str, content: str) -> bool:
        thread = self._threads.get(thread_id)
        if not thread:
            return False
        thread.notes.append(asdict(ResearchNote(content=content)))
        thread.updated_at = datetime.now().isoformat()
        return True

    def add_source(
        self, thread_id: str, url: str, title: str = "", snippet: str = "",
    ) -> bool:
        thread = self._threads.get(thread_id)
        if not thread:
            return False
        thread.sources.append({
            "url": url,
            "title": title,
            "snippet": snippet,
            "added_at": datetime.now().isoformat(),
        })
        thread.citations.append(f"[{len(thread.citations)+1}] {title}. {url}")
        thread.updated_at = datetime.now().isoformat()
        return True

    def add_follow_up(self, thread_id: str, question: str) -> Optional[str]:
        thread = self._threads.get(thread_id)
        if not thread:
            return None
        fu = FollowUp(question=question)
        fid = str(uuid.uuid4())
        thread.follow_ups.append({"id": fid, **asdict(fu)})
        thread.updated_at = datetime.now().isoformat()
        return fid

    def answer_follow_up(
        self, thread_id: str, follow_up_id: str, answer: str,
    ) -> bool:
        thread = self._threads.get(thread_id)
        if not thread:
            return False
        for fu in thread.follow_ups:
            if fu.get("id") == follow_up_id:
                fu["answered"] = True
                fu["answer"] = answer
                thread.updated_at = datetime.now().isoformat()
                return True
        return False

    def get_thread(self, thread_id: str) -> Optional[ResearchThread]:
        return self._threads.get(thread_id)

    def get_threads_by_project(self, project_id: str) -> list[ResearchThread]:
        return [
            t for t in self._threads.values()
            if t.project_id == project_id
        ]

    def get_active_threads(self) -> list[ResearchThread]:
        return [
            t for t in self._threads.values()
            if t.status == "active"
        ]

    def close_thread(self, thread_id: str) -> bool:
        thread = self._threads.get(thread_id)
        if not thread:
            return False
        thread.status = "completed"
        thread.updated_at = datetime.now().isoformat()
        return True

    def get_thread_summary(self, thread_id: str) -> str:
        thread = self._threads.get(thread_id)
        if not thread:
            return ""
        lines = [f"Research Thread: {thread.topic}"]
        if thread.summary:
            lines.append(f"Summary: {thread.summary}")
        lines.append(f"Notes: {len(thread.notes)}")
        lines.append(f"Sources: {len(thread.sources)}")
        answered = sum(1 for f in thread.follow_ups if f.get("answered"))
        total = len(thread.follow_ups)
        lines.append(f"Follow-ups: {answered}/{total} answered")
        lines.append(f"Status: {thread.status}")
        return "\n".join(lines)

    def get_all_threads(self) -> list[ResearchThread]:
        return list(self._threads.values())
