"""In-memory LRU conversation cache with TTL support.

Thread-safe: uses a threading.Lock for concurrent access.
"""

from __future__ import annotations

import time
import threading
from collections import OrderedDict
from typing import Optional


class ConversationCache:
    """LRU cache for conversation history with TTL eviction.

    Usage:
        cache = ConversationCache(max_size=50, ttl=3600)
        cache.set("session-1", messages)
        msgs = cache.get("session-1")
    """

    def __init__(self, max_size: int = 50, ttl: int = 3600):
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl

    def get(self, key: str) -> Optional[list]:
        """Retrieve messages by key. Returns None if missing or expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if time.time() - entry["time"] > self._ttl:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return entry["messages"]

    def set(self, key: str, messages: list) -> None:
        """Store messages by key. Evicts oldest if at capacity."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = {"messages": messages, "time": time.time()}
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        with self._lock:
            return len(self._cache)

    def invalidate(self, key: str) -> None:
        """Remove a specific entry."""
        with self._lock:
            self._cache.pop(key, None)
