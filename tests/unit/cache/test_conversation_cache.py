"""Tests for ConversationCache — LRU + TTL behavior."""

import time
from core.cache import ConversationCache


def test_get_set():
    cache = ConversationCache(max_size=10, ttl=3600)
    cache.set("key1", [{"role": "user", "content": "hello"}])
    msgs = cache.get("key1")
    assert msgs == [{"role": "user", "content": "hello"}]


def test_get_missing():
    cache = ConversationCache(max_size=10, ttl=3600)
    assert cache.get("nonexistent") is None


def test_get_expired():
    cache = ConversationCache(max_size=10, ttl=0.1)
    cache.set("key1", ["msg"])
    time.sleep(0.15)
    assert cache.get("key1") is None


def test_lru_eviction():
    cache = ConversationCache(max_size=3, ttl=3600)
    cache.set("a", [1])
    cache.set("b", [2])
    cache.set("c", [3])
    cache.set("d", [4])
    assert cache.get("a") is None  # evicted
    assert cache.get("b") is not None
    assert cache.get("c") is not None
    assert cache.get("d") is not None


def test_lru_reorder():
    cache = ConversationCache(max_size=2, ttl=3600)
    cache.set("a", [1])
    cache.set("b", [2])
    cache.get("a")  # touch
    cache.set("c", [3])
    assert cache.get("a") is not None  # recently used
    assert cache.get("b") is None  # evicted


def test_clear():
    cache = ConversationCache(max_size=10, ttl=3600)
    cache.set("a", [1])
    cache.set("b", [2])
    cache.clear()
    assert cache.size == 0
    assert cache.get("a") is None


def test_invalidate():
    cache = ConversationCache(max_size=10, ttl=3600)
    cache.set("a", [1])
    cache.invalidate("a")
    assert cache.get("a") is None


def test_size_property():
    cache = ConversationCache(max_size=10, ttl=3600)
    assert cache.size == 0
    cache.set("a", [1])
    assert cache.size == 1
    cache.set("b", [2])
    assert cache.size == 2


def test_set_overwrites_existing():
    cache = ConversationCache(max_size=10, ttl=3600)
    cache.set("a", [1])
    cache.set("a", [2])
    assert cache.get("a") == [2]
    assert cache.size == 1
