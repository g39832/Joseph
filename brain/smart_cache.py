"""
brain/smart_cache.py
---------------------
Smart Caching — Phase X.

Caches:
  - Project context (tasks, milestones, decisions)
  - Memory retrieval results (per query)
  - Research summaries (per topic)
  - System prompt fragments (per path)

Intelligent invalidation based on:
  - Time-to-live per cache type
  - Explicit invalidation on project changes
  - Session boundaries
"""

import logging
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TTLCache:
    """
    LRU cache with time-to-live per entry.

    Usage:
        cache = TTLCache(max_size=50, default_ttl=300)
        cache.set("project_ctx", data)
        cached = cache.get("project_ctx")
    """

    def __init__(self, max_size: int = 50, default_ttl: float = 300):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get a cached value. Returns None if missing or expired."""
        if key not in self._cache:
            self._misses += 1
            return None

        value, expiry, created = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            self._misses += 1
            return None

        self._cache.move_to_end(key)
        self._hits += 1
        return value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Set a cached value with TTL in seconds."""
        ttl = ttl if ttl is not None else self._default_ttl
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry, time.time())
        self._cache.move_to_end(key)

        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def invalidate_pattern(self, prefix: str) -> int:
        """Invalidate all keys starting with prefix."""
        keys = [k for k in self._cache if k.startswith(prefix)]
        for k in keys:
            del self._cache[k]
        return len(keys)

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = round(self._hits / total, 3) if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
        }


class SmartCache:
    """
    Intelligent caching layer for JOSEPH.

    Manages multiple TTL caches for different data types
    with appropriate default TTLs.

    Usage:
        cache = SmartCache()
        cache.set_project_context("proj-123", data)
        ctx = cache.get_project_context("proj-123")
    """

    PROJECT_TTL = 600
    MEMORY_TTL = 120
    RESEARCH_TTL = 900
    PROMPT_TTL = 300
    SYSTEM_CONTEXT_TTL = 60

    def __init__(self):
        self._project = TTLCache(max_size=20, default_ttl=self.PROJECT_TTL)
        self._memory = TTLCache(max_size=30, default_ttl=self.MEMORY_TTL)
        self._research = TTLCache(max_size=15, default_ttl=self.RESEARCH_TTL)
        self._prompt = TTLCache(max_size=10, default_ttl=self.PROMPT_TTL)
        self._system = TTLCache(max_size=5, default_ttl=self.SYSTEM_CONTEXT_TTL)
        self._all_caches = {
            "project": self._project,
            "memory": self._memory,
            "research": self._research,
            "prompt": self._prompt,
            "system": self._system,
        }

    # Project context
    def get_project_context(self, project_id: str) -> Optional[Any]:
        return self._project.get(f"project:{project_id}")

    def set_project_context(self, project_id: str, data: Any) -> None:
        self._project.set(f"project:{project_id}", data)

    def invalidate_project(self, project_id: str) -> None:
        self._project.invalidate(f"project:{project_id}")

    # Memory retrievals
    def get_memory(self, query_hash: str) -> Optional[Any]:
        return self._memory.get(f"mem:{query_hash}")

    def set_memory(self, query_hash: str, data: Any, ttl: Optional[float] = None) -> None:
        self._memory.set(f"mem:{query_hash}", data, ttl=ttl)

    def invalidate_memory(self, query_hash: str) -> None:
        self._memory.invalidate(f"mem:{query_hash}")

    def invalidate_all_memory(self) -> None:
        self._memory.invalidate_pattern("mem:")

    # Research summaries
    def get_research(self, topic: str) -> Optional[Any]:
        return self._research.get(f"research:{topic.lower()}")

    def set_research(self, topic: str, data: Any) -> None:
        self._research.set(f"research:{topic.lower()}", data)

    # Prompt fragments
    def get_prompt_fragment(self, path_name: str) -> Optional[Any]:
        return self._prompt.get(f"prompt:{path_name}")

    def set_prompt_fragment(self, path_name: str, data: str) -> None:
        self._prompt.set(f"prompt:{path_name}", data)

    # System context
    def get_system_context(self, session_id: str) -> Optional[Any]:
        return self._system.get(f"system:{session_id}")

    def set_system_context(self, session_id: str, data: Any) -> None:
        self._system.set(f"system:{session_id}", data)

    def invalidate_system_context(self, session_id: str) -> None:
        self._system.invalidate(f"system:{session_id}")

    # Bulk operations
    def invalidate_all(self) -> None:
        for cache in self._all_caches.values():
            cache.clear()

    def invalidate_project_data(self, project_id: str) -> None:
        self.invalidate_project(project_id)
        self.invalidate_all_memory()

    def get_stats(self) -> dict:
        return {
            name: cache.get_stats()
            for name, cache in self._all_caches.items()
        }


smart_cache = SmartCache()
