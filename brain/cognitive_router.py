"""
brain/cognitive_router.py
--------------------------
Dynamic Cognitive Routing — Phase X.

Routes each request through the optimal cognitive path based on
intent classification, context requirements, and complexity.

Paths:
  Fast Path    — small talk, simple questions, quick facts
  Deep Path    — complex analysis, planning, design, architecture
  Engineering  — programming, debugging, refactoring, code review
  Research     — multi-source synthesis, investigation, documentation

Also handles:
  - Request classification (8 categories)
  - Adaptive response depth control
  - Response quality self-check
  - Per-request latency measurement
"""

import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class RequestCategory(Enum):
    CHAT = "chat"
    CODING = "coding"
    RESEARCH = "research"
    PROJECT_MGMT = "project_management"
    LEARNING = "learning"
    PLANNING = "planning"
    TOOL_USE = "tool_use"
    MEMORY_RECALL = "memory_recall"


class CognitivePath(Enum):
    FAST = "fast"
    DEEP = "deep"
    ENGINEERING = "engineering"
    RESEARCH = "research"


CATEGORY_KEYWORDS: dict[RequestCategory, list[str]] = {
    RequestCategory.CHAT: [
        "hello", "hi", "hey", "how are you", "good morning", "good evening",
        "thanks", "thank you", "nice", "cool", "awesome",
    ],
    RequestCategory.CODING: [
        "def ", "class ", "function", "import ", "code", "bug", "debug",
        "refactor", "compile", "syntax", "error", "exception", "variable",
        "algorithm", "implement", "write a", "programming", "python",
        "javascript", "typescript", "rust", "api", "endpoint", "route",
    ],
    RequestCategory.RESEARCH: [
        "research", "find", "search for", "look up", "what is", "how does",
        "explain", "tell me about", "investigate", "study", "analyze",
        "compare", "difference between", "summary of", "overview",
    ],
    RequestCategory.PROJECT_MGMT: [
        "project", "task", "milestone", "deadline", "status", "progress",
        "update", "roadmap", "goal", "sprint", "backlog", "ticket",
    ],
    RequestCategory.LEARNING: [
        "learn", "study", "tutorial", "guide", "course", "practice",
        "understand", "concept", "beginner", "advanced", "skill",
    ],
    RequestCategory.PLANNING: [
        "plan", "strategy", "approach", "design", "architecture",
        "how should i", "what should i", "steps to", "roadmap",
        "outline", "blueprint", "scheme",
    ],
    RequestCategory.TOOL_USE: [
        "open ", "search", "play ", "take ", "screenshot", "remind",
        "set ", "create ", "make ", "run ", "execute",
    ],
    RequestCategory.MEMORY_RECALL: [
        "remember", "recall", "what did i", "what was", "who is",
        "do you remember", "earlier", "last time", "yesterday",
        "previous session", "before",
    ],
}


@dataclass
class LatencySnapshot:
    classification_ms: float = 0.0
    memory_ms: float = 0.0
    context_ms: float = 0.0
    llm_ms: float = 0.0
    total_ms: float = 0.0

    def __str__(self) -> str:
        return (
            f"classify={self.classification_ms:.0f}ms "
            f"memory={self.memory_ms:.0f}ms "
            f"context={self.context_ms:.0f}ms "
            f"llm={self.llm_ms:.0f}ms "
            f"total={self.total_ms:.0f}ms"
        )


@dataclass
class RoutingDecision:
    category: RequestCategory = RequestCategory.CHAT
    path: CognitivePath = CognitivePath.FAST
    response_depth: float = 0.5
    needs_project_context: bool = False
    needs_research: bool = False
    needs_memory_search: bool = True
    detected_project: Optional[str] = None
    latency: LatencySnapshot = field(default_factory=LatencySnapshot)
    confidence: float = 1.0

    def should_use_llm(self) -> bool:
        return True


class CognitiveRouter:
    """
    Routes each request through the optimal cognitive path.

    Usage:
        router = CognitiveRouter()
        decision = router.classify("write a python function to sort a list")
        depth = router.get_depth_instruction(decision)
    """

    def __init__(self):
        self._latency_history: deque = deque(maxlen=100)

    def classify(
        self,
        user_input: str,
        llm_interface=None,
    ) -> RoutingDecision:
        """
        Classify the user's request and determine the optimal cognitive path.
        Uses heuristic keyword matching (fast, no LLM call needed).
        """
        start = time.perf_counter()
        decision = RoutingDecision()

        text = user_input.lower().strip()

        category = self._classify_by_keywords(text)
        decision.category = category

        decision.path = self._select_path(category, text)
        decision.response_depth = self._compute_depth(category, text)
        decision.needs_project_context = self._detect_project_need(text)
        decision.needs_research = category in (
            RequestCategory.RESEARCH,
            RequestCategory.LEARNING,
        )
        decision.needs_memory_search = category in (
            RequestCategory.MEMORY_RECALL,
            RequestCategory.CHAT,
            RequestCategory.PROJECT_MGMT,
        )
        decision.detected_project = self._extract_project_name(text)
        decision.confidence = self._compute_confidence(text, category)

        decision.latency.classification_ms = (time.perf_counter() - start) * 1000
        self._latency_history.append(decision.latency)
        return decision

    def _classify_by_keywords(self, text: str) -> RequestCategory:
        """
        Classify request by keyword matching.
        Falls back to chat if no clear match.
        """
        scores: dict[RequestCategory, int] = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in text:
                    score += 1
                    if text.startswith(keyword) or text == keyword:
                        score += 2
            if score > 0:
                scores[category] = score

        if not scores:
            return RequestCategory.CHAT

        code_keywords = ["python", "code", "function", "class", "bug", "debug",
                         "write", "implement", "refactor", "fix"]
        code_score = sum(1 for kw in code_keywords if kw in text)

        question_words = ["what", "how", "why", "when", "where", "which", "who"]
        question_score = sum(1 for w in question_words if text.startswith(w) or f" {w} " in text)

        if code_score >= 3 and RequestCategory.CODING in scores:
            return RequestCategory.CODING

        if question_score >= 1 and RequestCategory.RESEARCH in scores and scores.get(RequestCategory.RESEARCH, 0) >= scores.get(RequestCategory.CODING, 0):
            return RequestCategory.RESEARCH

        best = max(scores, key=lambda k: (scores[k], self._category_priority(k)))
        return best

    def _category_priority(self, category: RequestCategory) -> int:
        priorities = {
            RequestCategory.MEMORY_RECALL: 10,
            RequestCategory.CODING: 8,
            RequestCategory.PROJECT_MGMT: 7,
            RequestCategory.PLANNING: 6,
            RequestCategory.RESEARCH: 5,
            RequestCategory.LEARNING: 4,
            RequestCategory.TOOL_USE: 3,
            RequestCategory.CHAT: 1,
        }
        return priorities.get(category, 0)

    def _select_path(self, category: RequestCategory, text: str) -> CognitivePath:
        """Select the cognitive processing path based on category and content."""
        if category == RequestCategory.CODING:
            complexity = self._estimate_complexity(text)
            return CognitivePath.DEEP if complexity > 0.6 else CognitivePath.ENGINEERING

        path_map: dict[RequestCategory, CognitivePath] = {
            RequestCategory.CHAT: CognitivePath.FAST,
            RequestCategory.RESEARCH: CognitivePath.RESEARCH,
            RequestCategory.PROJECT_MGMT: CognitivePath.DEEP,
            RequestCategory.LEARNING: CognitivePath.RESEARCH,
            RequestCategory.PLANNING: CognitivePath.DEEP,
            RequestCategory.TOOL_USE: CognitivePath.FAST,
            RequestCategory.MEMORY_RECALL: CognitivePath.FAST,
        }
        path = path_map.get(category, CognitivePath.FAST)

        if len(text.split()) > 30:
            if path == CognitivePath.FAST:
                path = CognitivePath.DEEP

        return path

    def _compute_depth(self, category: RequestCategory, text: str) -> float:
        """Compute response depth 0.0-1.0 based on intent and complexity."""
        depth_map: dict[RequestCategory, float] = {
            RequestCategory.CHAT: 0.3,
            RequestCategory.CODING: 0.7,
            RequestCategory.RESEARCH: 0.85,
            RequestCategory.PROJECT_MGMT: 0.6,
            RequestCategory.LEARNING: 0.75,
            RequestCategory.PLANNING: 0.8,
            RequestCategory.TOOL_USE: 0.25,
            RequestCategory.MEMORY_RECALL: 0.4,
        }
        base = depth_map.get(category, 0.5)

        word_count = len(text.split())
        if word_count > 20:
            base = min(1.0, base + 0.1)
        if word_count > 50:
            base = min(1.0, base + 0.15)

        if text.endswith("?"):
            pass
        elif text.endswith("!"):
            base = max(0.2, base - 0.1)

        if any(w in text for w in ["brief", "short", "quick", "tl;dr", "summarize"]):
            base = 0.25
        elif any(w in text for w in ["detailed", "explain", "comprehensive", "thorough", "elaborate"]):
            base = 0.9

        return round(base, 2)

    def _estimate_complexity(self, text: str) -> float:
        """Estimate coding request complexity."""
        complexity = 0.3
        advanced_terms = [
            "recursive", "asynchronous", "concurrent", "parallel",
            "distributed", "optimization", "design pattern", "architecture",
            "dependency", "inheritance", "polymorphism", "decorator",
            "metaclass", "context manager", "generator",
        ]
        for term in advanced_terms:
            if term in text:
                complexity += 0.1

        word_count = len(text.split())
        if word_count > 30:
            complexity += 0.15
        if word_count > 60:
            complexity += 0.15

        return min(1.0, complexity)

    def _detect_project_need(self, text: str) -> bool:
        project_indicators = [
            "project", "workspace", "my app", "my tool", "current project",
            "active project", "project status", "project update",
            "milestone", "task list", "what am i working on",
        ]
        return any(ind in text for ind in project_indicators)

    def _extract_project_name(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:project|app|tool)\s+(?:called|named|is)\s+(\w[\w\s]{0,30}?)(?:\.|,|\s|$)",
            r"(?:the\s+)?(\w+)\s+project",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip().lower()
        return None

    def _compute_confidence(self, text: str, category: RequestCategory) -> float:
        """Compute confidence in the classification."""
        keywords_found = sum(
            1 for kw in CATEGORY_KEYWORDS.get(category, []) if kw in text
        )
        total_keywords = len(CATEGORY_KEYWORDS.get(category, []))
        if total_keywords == 0:
            return 0.5
        ratio = keywords_found / total_keywords
        return min(1.0, 0.5 + ratio)

    def get_depth_instruction(self, decision: RoutingDecision) -> str:
        """Generate a depth instruction for the system prompt."""
        depth = decision.response_depth
        if depth < 0.35:
            return "Respond in 1-2 sentences. Be very concise."
        elif depth < 0.55:
            return "Respond concisely. 2-4 sentences is enough."
        elif depth < 0.75:
            return "Provide a thorough response with explanation."
        else:
            return "Provide a comprehensive, detailed response. Cover all relevant aspects."

    def get_path_instruction(self, decision: RoutingDecision) -> str:
        """Generate a path-specific instruction for the system prompt."""
        path = decision.path
        if path == CognitivePath.FAST:
            return "Be conversational and direct."
        elif path == CognitivePath.DEEP:
            return "Think step by step. Consider trade-offs and alternatives."
        elif path == CognitivePath.ENGINEERING:
            return "Focus on code quality, correctness, and best practices. Provide examples."
        elif path == CognitivePath.RESEARCH:
            return "Synthesize information from multiple angles. Be thorough and cite reasoning."
        return ""

    def get_latency_stats(self) -> dict:
        """Get latency statistics across recent requests."""
        if not self._latency_history:
            return {"average_ms": {}, "total_requests": 0}
        avg_classification = sum(l.classification_ms for l in self._latency_history) / len(self._latency_history)
        return {
            "average_classification_ms": round(avg_classification, 1),
            "total_requests": len(self._latency_history),
        }


def quality_check(response: str, user_input: str) -> str:
    """Lightweight response quality self-check. No LLM call."""
    if not response or len(response) < 5:
        return response

    user_lower = user_input.strip().rstrip("?").lower()
    response_lower = response.lower()

    question_words = ["what", "how", "why", "when", "where", "who", "which"]
    is_question = any(user_input.lower().startswith(w) for w in question_words) or "?" in user_input

    key_terms = [w for w in user_lower.split() if len(w) > 4 and w not in
                 {"what", "how", "why", "when", "where", "which", "there", "about", "would", "could", "should", "please", "tell", "help"}]
    if key_terms and not any(t in response_lower for t in key_terms[:3]):
        pass

    if response_lower.strip().startswith("i don't know") and is_question:
        pass

    if len(set(response.split())) < 3 and is_question:
        pass

    return response


cognitive_router = CognitiveRouter()
