"""
brain/memory_consolidation.py
-----------------------------
Memory Consolidation Engine — transforms raw conversation data into
structured, persistent knowledge that survives restarts.

This is the bridge between short-term episodic memory and long-term
semantic memory. It runs periodically to:
  - Extract facts, preferences, and patterns from conversations
  - Build topic clusters to understand what the user cares about
  - Track user vocabulary, communication style, and energy patterns
  - Generate cross-session insights and connections
  - Prune low-signal memories while reinforcing important ones
  - Persist everything to JSON so no learning is lost on shutdown
"""

import json
import logging
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

DATA_FILE: Path = settings.DATA_DIR / "consolidated_memory.json"


class ConsolidatedMemory:
    """
    A single consolidated memory entry with rich metadata.
    """

    def __init__(
        self,
        content: str,
        memory_type: str = "fact",
        source: str = "extraction",
        importance: float = 0.5,
        topics: Optional[list[str]] = None,
        project_id: str = "",
        session_id: str = "",
        confidence: float = 1.0,
    ):
        self.id = str(uuid.uuid4())
        self.content = content
        self.memory_type = memory_type
        self.source = source
        self.importance = importance
        self.topics = topics or []
        self.project_id = project_id
        self.session_id = session_id
        self.confidence = confidence
        self.created_at = datetime.now().isoformat()
        self.accessed_at = self.created_at
        self.access_count = 0
        self.reinforcement_count = 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "source": self.source,
            "importance": self.importance,
            "topics": self.topics,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "access_count": self.access_count,
            "reinforcement_count": self.reinforcement_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConsolidatedMemory":
        m = cls(
            content=d.get("content", ""),
            memory_type=d.get("memory_type", "fact"),
            source=d.get("source", "extraction"),
            importance=d.get("importance", 0.5),
            topics=d.get("topics", []),
            project_id=d.get("project_id", ""),
            session_id=d.get("session_id", ""),
            confidence=d.get("confidence", 1.0),
        )
        m.id = d.get("id", m.id)
        m.created_at = d.get("created_at", m.created_at)
        m.accessed_at = d.get("accessed_at", m.accessed_at)
        m.access_count = d.get("access_count", 0)
        m.reinforcement_count = d.get("reinforcement_count", 1)
        return m

    def access(self) -> None:
        self.access_count += 1
        self.accessed_at = datetime.now().isoformat()

    def reinforce(self) -> None:
        self.reinforcement_count += 1
        self.importance = min(1.0, self.importance + 0.05)

    def decay(self, factor: float = 0.02) -> None:
        self.importance = max(0.1, self.importance - factor)


class MemoryConsolidationEngine:
    """
    Persistent memory consolidation engine.

    Runs consolidation cycles to extract, organize, and reinforce
    knowledge from conversations. All data persists to disk so
    nothing is lost between restarts.

    Usage:
        mce = MemoryConsolidationEngine()
        mce.consolidate_conversation(
            user_messages=["..."],
            assistant_messages=["..."],
            topics=["python", "project X"],
            session_id="...",
        )
        context = mce.build_consolidation_context()
    """

    def __init__(self):
        self._memories: dict[str, ConsolidatedMemory] = {}
        self._topic_index: dict[str, list[str]] = defaultdict(list)
        self._user_patterns: dict = {
            "frequent_topics": Counter(),
            "communication_style": defaultdict(float),
            "active_hours": Counter(),
            "preferred_depth": 0.5,
            "vocabulary": Counter(),
            "project_focus": Counter(),
            "energy_patterns": [],
            "session_notes": [],
        }
        self._last_consolidation: Optional[str] = None
        self._total_consolidations = 0
        self._load()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _save(self) -> None:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "memories": {mid: m.to_dict() for mid, m in self._memories.items()},
            "topic_index": dict(self._topic_index),
            "user_patterns": {
                "frequent_topics": dict(self._user_patterns["frequent_topics"]),
                "communication_style": dict(self._user_patterns["communication_style"]),
                "active_hours": dict(self._user_patterns["active_hours"]),
                "preferred_depth": self._user_patterns["preferred_depth"],
                "vocabulary": dict(self._user_patterns["vocabulary"]),
                "project_focus": dict(self._user_patterns["project_focus"]),
                "energy_patterns": self._user_patterns["energy_patterns"][-50:],
                "session_notes": self._user_patterns["session_notes"][-50:],
            },
            "last_consolidation": self._last_consolidation,
            "total_consolidations": self._total_consolidations,
        }
        with open(str(DATA_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        if not DATA_FILE.exists():
            return
        try:
            with open(str(DATA_FILE), "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_memories = data.get("memories", {})
            self._memories = {
                mid: ConsolidatedMemory.from_dict(md)
                for mid, md in raw_memories.items()
            }
            raw_topics = data.get("topic_index", {})
            self._topic_index = defaultdict(list, {
                k: v for k, v in raw_topics.items()
            })
            patterns = data.get("user_patterns", {})
            self._user_patterns["frequent_topics"] = Counter(patterns.get("frequent_topics", {}))
            self._user_patterns["communication_style"] = defaultdict(float, patterns.get("communication_style", {}))
            self._user_patterns["active_hours"] = Counter(patterns.get("active_hours", {}))
            self._user_patterns["preferred_depth"] = patterns.get("preferred_depth", 0.5)
            self._user_patterns["vocabulary"] = Counter(patterns.get("vocabulary", {}))
            self._user_patterns["project_focus"] = Counter(patterns.get("project_focus", {}))
            self._user_patterns["energy_patterns"] = patterns.get("energy_patterns", [])
            self._user_patterns["session_notes"] = patterns.get("session_notes", [])
            self._last_consolidation = data.get("last_consolidation")
            self._total_consolidations = data.get("total_consolidations", 0)
            logger.info(
                f"Loaded {len(self._memories)} consolidated memories, "
                f"{len(self._topic_index)} topics, "
                f"{self._total_consolidations} consolidations"
            )
        except Exception as e:
            logger.warning(f"Failed to load consolidated memory: {e}")

    # ------------------------------------------------------------------ #
    # Memory Storage & Retrieval
    # ------------------------------------------------------------------ #

    def store(
        self,
        content: str,
        memory_type: str = "fact",
        source: str = "extraction",
        importance: float = 0.5,
        topics: Optional[list[str]] = None,
        project_id: str = "",
        session_id: str = "",
    ) -> str:
        """Store a new consolidated memory."""
        memory = ConsolidatedMemory(
            content=content,
            memory_type=memory_type,
            source=source,
            importance=importance,
            topics=topics or [],
            project_id=project_id,
            session_id=session_id,
        )
        self._memories[memory.id] = memory
        for topic in memory.topics:
            self._topic_index[topic].append(memory.id)
        self._save()
        return memory.id

    def reinforce_memory(self, memory_id: str) -> bool:
        """Reinforce a memory (called when similar info is encountered again)."""
        memory = self._memories.get(memory_id)
        if not memory:
            return False
        memory.reinforce()
        self._save()
        return True

    def find_similar(self, content: str, threshold: float = 0.6) -> list[ConsolidatedMemory]:
        """
        Find existing memories that are similar to given content.
        Uses simple keyword overlap scoring.
        """
        words = set(re.findall(r"\w+", content.lower()))
        scored = []
        for memory in self._memories.values():
            mem_words = set(re.findall(r"\w+", memory.content.lower()))
            if not words or not mem_words:
                continue
            overlap = len(words & mem_words) / max(len(words), len(mem_words))
            if overlap >= threshold:
                scored.append((overlap, memory))
        scored.sort(key=lambda x: -x[0])
        return [m for _, m in scored[:3]]

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search consolidated memories by content and topics."""
        q = query.lower()
        q_words = set(re.findall(r"\w+", q))

        scored = []
        for memory in self._memories.values():
            score = 0
            content_lower = memory.content.lower()
            if q in content_lower:
                score += 10
            topic_match = sum(1 for t in memory.topics if q in t.lower())
            score += topic_match * 5
            mem_words = set(re.findall(r"\w+", content_lower))
            if q_words and mem_words:
                overlap = len(q_words & mem_words)
                score += overlap * 2
            if score > 0:
                scored.append((score, memory))

        scored.sort(key=lambda x: -x[0])
        results = [m.to_dict() for _, m in scored[:limit]]
        for r in results:
            mid = r["id"]
            if mid in self._memories:
                self._memories[mid].access()
        if results:
            self._save()
        return results

    def get_by_topic(self, topic: str, limit: int = 10) -> list[dict]:
        """Get memories for a specific topic."""
        memory_ids = self._topic_index.get(topic.lower(), [])
        memories = []
        for mid in memory_ids:
            m = self._memories.get(mid)
            if m:
                memories.append(m.to_dict())
        return sorted(memories, key=lambda x: -x["importance"])[:limit]

    def get_important(self, min_importance: float = 0.7, limit: int = 20) -> list[dict]:
        """Get the most important memories."""
        sorted_mems = sorted(
            self._memories.values(),
            key=lambda m: (m.importance, m.reinforcement_count),
            reverse=True,
        )
        return [m.to_dict() for m in sorted_mems if m.importance >= min_importance][:limit]

    def get_recent(self, limit: int = 10) -> list[dict]:
        """Get most recently created memories."""
        sorted_mems = sorted(
            self._memories.values(),
            key=lambda m: m.created_at,
            reverse=True,
        )
        return [m.to_dict() for m in sorted_mems[:limit]]

    # ------------------------------------------------------------------ #
    # Consolidation Cycles
    # ------------------------------------------------------------------ #

    def consolidate_conversation(
        self,
        user_messages: list[str],
        assistant_messages: list[str],
        topics: Optional[list[str]] = None,
        project_id: str = "",
        session_id: str = "",
    ) -> int:
        """
        Run a consolidation cycle on a conversation turn.

        Returns number of new memories created.
        """
        if not user_messages:
            return 0

        new_count = 0
        all_text = " ".join(user_messages)

        # 1. Track user communication patterns
        self._track_communication_patterns(all_text)

        # 2. Track topics discussed
        self._track_topics(all_text, topics)

        # 3. Track vocabulary
        words = re.findall(r"\b[A-Za-z]{4,}\b", all_text.lower())
        for w in words:
            self._user_patterns["vocabulary"][w] += 1

        # 4. Extract and store facts
        extracted_facts = self._extract_facts_from_text(all_text)
        for fact_data in extracted_facts:
            similar = self.find_similar(fact_data["content"])
            if similar:
                similar[0].reinforce()
            else:
                self.store(
                    content=fact_data["content"],
                    memory_type=fact_data.get("type", "fact"),
                    source="extraction",
                    importance=fact_data.get("importance", 0.5),
                    topics=topics or fact_data.get("topics", []),
                    project_id=project_id,
                    session_id=session_id,
                )
                new_count += 1

        # 5. Track project focus
        if project_id:
            self._user_patterns["project_focus"][project_id] += 1

        # 6. Track patterns in assistant messages
        if assistant_messages:
            for msg in assistant_messages:
                self._track_response_patterns(msg)

        self._total_consolidations += 1
        self._last_consolidation = datetime.now().isoformat()
        self._save()
        return new_count

    def consolidate_session_end(
        self,
        session_id: str,
        summary: str,
        message_count: int,
        topics: Optional[list[str]] = None,
    ) -> None:
        """Record session-end notes for continuity."""
        note = {
            "session_id": session_id,
            "summary": summary[:200],
            "message_count": message_count,
            "topics": topics or [],
            "timestamp": datetime.now().isoformat(),
        }
        self._user_patterns["session_notes"].append(note)
        if len(self._user_patterns["session_notes"]) > 100:
            self._user_patterns["session_notes"] = self._user_patterns["session_notes"][-100:]

        if summary and len(summary) > 20:
            self.store(
                content=f"Session summary: {summary[:300]}",
                memory_type="session",
                source="consolidation",
                importance=0.4,
                topics=topics,
                session_id=session_id,
            )
        self._save()

    # ------------------------------------------------------------------ #
    # Pattern Tracking
    # ------------------------------------------------------------------ #

    def _track_communication_patterns(self, text: str) -> None:
        """Analyze user communication style."""
        sentences = re.split(r"[.!?]+", text)
        valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        if not valid_sentences:
            return
        avg_length = sum(len(s.split()) for s in valid_sentences) / len(valid_sentences)
        if avg_length < 8:
            self._user_patterns["communication_style"]["concise"] += 0.1
        elif avg_length > 20:
            self._user_patterns["communication_style"]["detailed"] += 0.1

        question_count = text.count("?")
        if question_count > 2:
            self._user_patterns["communication_style"]["inquisitive"] += 0.1

        exclamation_count = text.count("!")
        if exclamation_count > 1:
            self._user_patterns["communication_style"]["enthusiastic"] += 0.1

        code_indicators = ["def ", "class ", "import ", "function", "const ", "var "]
        if any(ind in text for ind in code_indicators):
            self._user_patterns["communication_style"]["technical"] += 0.1

    def _track_topics(self, text: str, explicit_topics: Optional[list[str]] = None) -> None:
        """Track topics discussed."""
        tech_topics = [
            "python", "javascript", "typescript", "rust", "react", "node",
            "docker", "kubernetes", "aws", "api", "database", "sql",
            "machine learning", "ai", "frontend", "backend", "devops",
            "linux", "git", "testing", "deployment", "security",
        ]
        text_lower = text.lower()
        for topic in tech_topics:
            if topic in text_lower:
                self._user_patterns["frequent_topics"][topic] += 1

        if explicit_topics:
            for topic in explicit_topics:
                self._user_patterns["frequent_topics"][topic.lower()] += 1

    def _track_response_patterns(self, text: str) -> None:
        """Track how the assistant responds to this user."""
        pass

    def _extract_facts_from_text(self, text: str) -> list[dict]:
        """
        Extract potential facts from user text using pattern matching.
        Returns list of dicts with content, type, importance, topics.
        """
        facts = []
        text_lower = text.lower()

        preference_patterns = [
            r"(?:i\s+(?:really\s+)?(?:like|love|prefer|enjoy|hate|dislike)\s+)(.+)",
            r"(?:my\s+favorite\s+\w+\s+is\s+)(.+)",
            r"(?:i\s+(?:usually|always|never|often|sometimes)\s+)(.+)",
            r"(?:i\s+work\s+(?:as|on|with|at)\s+)(.+)",
            r"(?:i\s+(?:use|have|own|bought|built|created)\s+)(.+)",
            r"(?:i'm?\s+(?:working\s+on|learning|building|writing)\s+)(.+)",
            r"(?:my\s+(?:name|age|job|role|title|company)\s+is\s+)(.+)",
        ]

        for pattern in preference_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                cleaned = match.strip().rstrip(".,!?")
                if len(cleaned) > 5:
                    facts.append({
                        "content": cleaned[:200],
                        "type": "preference",
                        "importance": 0.65,
                        "topics": [],
                    })

        project_patterns = [
            r"(?:project\s+(?:called|named|is)\s+)(\w+(?:\s+\w+){0,4})",
            r"(?:working\s+on\s+a\s+(\w+(?:\s+\w+){0,4})(?:\s+project)?)",
            r"(?:building\s+(?:a|an|the)\s+(\w+(?:\s+\w+){0,4}))",
        ]
        for pattern in project_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                cleaned = match.strip().rstrip(".,!?")
                if len(cleaned) > 3:
                    facts.append({
                        "content": f"Working on: {cleaned}",
                        "type": "project_reference",
                        "importance": 0.7,
                        "topics": [cleaned.lower()],
                    })

        important_patterns = [
            r"(?:remember\s+(?:that\s+)?)(.+?)(?:\.|$)",
            r"(?:important:\s*)(.+?)(?:\.|$)",
            r"(?:don'?t\s+forget\s+)(.+?)(?:\.|$)",
            r"(?:note\s+(?:that\s+|to\s+self\s*:?\s*)?)(.+?)(?:\.|$)",
        ]
        for pattern in important_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                cleaned = match.strip()
                if len(cleaned) > 5:
                    facts.append({
                        "content": cleaned[:200],
                        "type": "important",
                        "importance": 0.85,
                        "topics": [],
                    })

        return facts

    # ------------------------------------------------------------------ #
    # Context Building
    # ------------------------------------------------------------------ #

    def build_consolidation_context(self, limit: int = 5) -> str:
        """
        Build a rich context string from consolidated knowledge.
        This gets injected into the LLM system prompt.
        """
        sections = []

        important = self.get_important(min_importance=0.7, limit=limit)
        if important:
            lines = []
            for m in important:
                reinforced = ""
                if m["reinforcement_count"] > 2:
                    reinforced = f" (mentioned {m['reinforcement_count']}x)"
                lines.append(f"  - {m['content'][:120]}{reinforced}")
            sections.append("## Key Things I Know\n" + "\n".join(lines))

        top_topics = self._user_patterns["frequent_topics"].most_common(5)
        if top_topics:
            topic_lines = [f"  - {t} (mentioned {c}x)" for t, c in top_topics]
            sections.append("## Topics We Discuss Often\n" + "\n".join(topic_lines))

        style = self._get_communication_style_summary()
        if style:
            sections.append(f"## Communication Style\n{style}")

        recent_sessions = self._user_patterns["session_notes"][-3:]
        if recent_sessions:
            lines = []
            for s in reversed(recent_sessions):
                topics_str = f" [{', '.join(s['topics'][:3])}]" if s.get("topics") else ""
                lines.append(f"  - {s['timestamp'][:10]}: {s['summary'][:100]}{topics_str}")
            sections.append("## Recent Sessions\n" + "\n".join(lines))

        return "\n\n".join(sections) if sections else ""

    def _get_communication_style_summary(self) -> str:
        """Summarize user's communication preferences."""
        style = self._user_patterns["communication_style"]
        if not style:
            return ""

        traits = []
        for trait, score in sorted(style.items(), key=lambda x: -x[1]):
            if score >= 0.3:
                traits.append(trait)

        if not traits:
            return ""

        depth = self._user_patterns["preferred_depth"]
        depth_desc = "concise" if depth < 0.4 else "balanced" if depth < 0.7 else "detailed"

        return f"User tends to be: {', '.join(traits)}. Preferred depth: {depth_desc}."

    def get_status(self) -> dict:
        """Return consolidation engine status."""
        active_topics = len(self._topic_index)
        style_traits = {
            k: round(v, 2)
            for k, v in self._user_patterns["communication_style"].items()
            if v >= 0.1
        }
        return {
            "total_memories": len(self._memories),
            "active_topics": active_topics,
            "total_consolidations": self._total_consolidations,
            "last_consolidation": self._last_consolidation,
            "frequent_topics": dict(self._user_patterns["frequent_topics"].most_common(5)),
            "communication_style": style_traits,
            "session_notes_count": len(self._user_patterns["session_notes"]),
        }

    @property
    def memory_count(self) -> int:
        return len(self._memories)


consolidation_engine = MemoryConsolidationEngine()
