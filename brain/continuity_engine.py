"""
brain/continuity_engine.py
----------------------------
Long-term Continuity — maintains awareness across weeks and months.

Now enhanced with rich cross-session tracking:
  - Topics discussed per session with frequency
  - Conversation themes and emotional tone
  - Tasks mentioned as "to do" or "follow up"
  - What the user was actively working on
  - Unfinished business and stalled items
  - Meaningful continuity narrative for LLM injection
"""

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

DATA_FILE: Path = settings.DATA_DIR / "continuity.json"


class ContinuityEngine:
    """
    Enhanced cross-session continuity tracker.

    Usage:
        ce = ContinuityEngine(workspace_manager, project_commander,
                              activity_tracker, project_store)
        ctx = ce.get_continuity_context()
        ce.record_session_end()
    """

    def __init__(
        self,
        workspace_manager=None,
        project_commander=None,
        activity_tracker=None,
        project_store=None,
        decision_history=None,
    ):
        self._wm = workspace_manager
        self._pc = project_commander
        self._tracker = activity_tracker
        self._ps = project_store
        self._dh = decision_history
        self._sessions: list[dict] = []
        self._session_notes: list[dict] = []
        self._topic_trends: Counter = Counter()
        self._user_goals: list[dict] = []
        self._follow_ups: list[dict] = []
        self._load()

    def record_session_start(self) -> None:
        now = datetime.now().isoformat()
        self._sessions.append({
            "start": now,
            "end": "",
            "topics": [],
            "themes": [],
            "tone": "neutral",
            "key_moments": [],
        })
        self._save()

    def record_session_end(self) -> None:
        if self._sessions:
            self._sessions[-1]["end"] = datetime.now().isoformat()
            self._save()

    def record_turn(self, user_message: str, assistant_message: str) -> None:
        """
        Record a single conversational turn for continuity analysis.
        Extracts topics, goals, follow-ups, and tone.
        """
        if not self._sessions:
            return

        session = self._sessions[-1]
        text = user_message.lower()

        topics = self._extract_topics(text)
        session["topics"].extend(topics)
        for t in topics:
            self._topic_trends[t] += 1

        goals = self._extract_goals(text)
        for g in goals:
            self._user_goals.append({
                "goal": g,
                "timestamp": datetime.now().isoformat(),
                "status": "active",
            })
            session["key_moments"].append(f"Goal: {g}")

        follow_ups = self._extract_follow_ups(text)
        for f in follow_ups:
            self._follow_ups.append({
                "item": f,
                "timestamp": datetime.now().isoformat(),
                "resolved": False,
            })

    def record_note(self, summary: str, project_id: str = "") -> None:
        self._session_notes.append({
            "summary": summary,
            "project_id": project_id,
            "timestamp": datetime.now().isoformat(),
        })
        if len(self._session_notes) > 100:
            self._session_notes = self._session_notes[-100:]
        self._save()

    def _extract_topics(self, text: str) -> list[str]:
        topics = []
        tech_keywords = {
            "python", "javascript", "typescript", "rust", "go", "react",
            "docker", "kubernetes", "aws", "database", "api", "frontend",
            "backend", "devops", "linux", "git", "testing", "ai", "ml",
            "machine learning", "security", "deployment", "sql",
        }
        for word in tech_keywords:
            if word in text:
                topics.append(word)

        project_match = re.search(r"(?:project|app|tool)\s+(?:called|named|is\s*:?\s*)?\s*(\w[\w\s]{1,30}?)(?:\.|,|\s|$)", text)
        if project_match:
            topics.append(project_match.group(1).strip().lower())

        return topics

    def _extract_goals(self, text: str) -> list[str]:
        goals = []
        patterns = [
            r"(?:i\s+(?:want|need|would\s+like|'m\s+trying|hope)\s+to\s+)(.+?)(?:\.|,|$)",
            r"(?:my\s+(?:goal|aim|objective)\s+(?:is|was)\s+to\s+)(.+?)(?:\.|,|$)",
            r"(?:i\s+(?:should|need\s+to|have\s+to|plan\s+to)\s+)(.+?)(?:\.|,|$)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                cleaned = m.strip().rstrip(".,!?").lower()
                if len(cleaned) > 5:
                    goals.append(cleaned[:120])
        return goals

    def _extract_follow_ups(self, text: str) -> list[str]:
        follow_ups = []
        patterns = [
            r"(?:remind\s+me\s+to\s+)(.+?)(?:\.|,|$)",
            r"(?:follow\s+up\s+(?:on|with)\s+)(.+?)(?:\.|,|$)",
            r"(?:i['']?ll\s+(?:check|look\s+into|get\s+back|come\s+back)\s+)(.+?)(?:\.|,|$)",
            r"(?:next\s+(?:time|step|thing)\s+(?:is|i['']?ll)\s+)(.+?)(?:\.|,|$)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                cleaned = m.strip().rstrip(".,!?").lower()
                if len(cleaned) > 5:
                    follow_ups.append(cleaned[:120])
        return follow_ups

    def get_continuity_context(self) -> str:
        """
        Build a rich continuity context string for LLM injection.
        """
        sections = []

        if not self._sessions:
            return ""

        sections.append("# Continuity Context")

        total = len(self._sessions)
        first = self._sessions[0]["start"][:10]
        last_session = self._sessions[-1]["start"][:10]
        sections.append(f"{total} sessions from {first} to {last_session}")

        if len(self._sessions) >= 2:
            prev = self._sessions[-2]
            prev_start = prev.get("start", "")[:16]
            prev_end = prev.get("end", "")[:16]
            duration = ""
            if prev_start and prev_end:
                try:
                    start_dt = datetime.fromisoformat(prev_start)
                    end_dt = datetime.fromisoformat(prev_end)
                    mins = int((end_dt - start_dt).total_seconds() / 60)
                    if mins > 0:
                        duration = f" ({mins} min)"
                except Exception:
                    pass
            sections.append(f"Previous session: {prev_start}{duration}")

            if prev.get("topics"):
                topic_counts = Counter(prev["topics"])
                top_topics = [t for t, _ in topic_counts.most_common(5)]
                sections.append(f"Topics discussed: {', '.join(top_topics)}")

            if prev.get("key_moments"):
                moments = prev["key_moments"][-5:]
                sections.append("Key moments from last session:")
                for m in moments:
                    sections.append(f"  - {m}")

        active_goals = [g for g in self._user_goals if g.get("status") == "active"][-5:]
        if active_goals:
            sections.append("Active goals:")
            for g in active_goals:
                sections.append(f"  - {g['goal'][:80]}")

        pending_followups = [f for f in self._follow_ups if not f.get("resolved")][-5:]
        if pending_followups:
            sections.append("Pending follow-ups:")
            for f in pending_followups:
                sections.append(f"  - {f['item'][:80]}")

        recent_notes = self._session_notes[-3:]
        if recent_notes:
            sections.append("Session notes:")
            for n in reversed(recent_notes):
                sections.append(f"  - {n['timestamp'][:10]}: {n['summary'][:100]}")

        if self._topic_trends:
            top_trending = self._topic_trends.most_common(5)
            sections.append("Overall topic frequency:")
            for topic, count in top_trending:
                sections.append(f"  - {topic}: {count}x")

        unfinished = self._detect_unfinished()
        if unfinished:
            sections.append("Unfinished:")
            for u in unfinished:
                sections.append(f"  - {u}")

        if self._dh:
            recent = self._dh.get_recent(limit=3)
            if recent:
                sections.append("Recent decisions:")
                for d in recent:
                    sections.append(f"  - {d.title}")

        return "\n".join(sections)

    def get_session_history_summary(self) -> str:
        if not self._sessions:
            return "No session history yet."
        total = len(self._sessions)
        first = self._sessions[0]["start"][:10]
        last = self._sessions[-1]["start"][:10]
        return f"{total} sessions from {first} to {last}"

    def resolve_follow_up(self, item: str) -> bool:
        for f in self._follow_ups:
            if f["item"] == item and not f["resolved"]:
                f["resolved"] = True
                f["resolved_at"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def resolve_goal(self, goal: str) -> bool:
        for g in self._user_goals:
            if g["goal"] == goal and g["status"] == "active":
                g["status"] = "completed"
                g["completed_at"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def _detect_unfinished(self) -> list[str]:
        unfinished = []
        if not self._pc or not self._ps:
            return unfinished

        try:
            for proj in self._ps.get_active_projects():
                status = self._pc.get_status(proj.id)
                open_t = status.get("open_tasks", 0)
                if open_t > 0:
                    unfinished.append(
                        f"{proj.name}: {open_t} open tasks "
                        f"(progress: {status.get('progress_pct', 0)}%)"
                    )
        except Exception:
            pass

        return unfinished[:5]

    def _save(self) -> None:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "sessions": self._sessions,
            "session_notes": self._session_notes,
            "topic_trends": dict(self._topic_trends),
            "user_goals": self._user_goals[-50:],
            "follow_ups": self._follow_ups[-50:],
        }
        with open(str(DATA_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        if not DATA_FILE.exists():
            return
        try:
            with open(str(DATA_FILE), "r", encoding="utf-8") as f:
                data = json.load(f)
            self._sessions = data.get("sessions", [])
            self._session_notes = data.get("session_notes", [])
            self._topic_trends = Counter(data.get("topic_trends", {}))
            self._user_goals = data.get("user_goals", [])
            self._follow_ups = data.get("follow_ups", [])
        except Exception as e:
            logger.warning(f"Failed to load continuity data: {e}")
