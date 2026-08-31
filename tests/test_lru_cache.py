"""Tests for LeastRecentlyUsedCache."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cache.lru import LeastRecentlyUsedCache


def test_lru_example_from_assignment() -> None:
    cache = LeastRecentlyUsedCache(3)
    assert cache.try_get("foo") is None
    cache.put("foo", "bar")
    assert cache.try_get("foo") == "bar"
    cache.clear()
    cache.put("a", "apple")
    cache.put("b", "bank")
    cache.put("c", "clue")
    assert cache.try_get("b") == "bank"
    cache.put("g", "gravity")
    assert cache.try_get("a") is None
    assert cache.try_get("g") == "gravity"


def test_remove_and_upsert() -> None:
    cache = LeastRecentlyUsedCache(2)
    cache.put("x", 1)
    cache.put("y", 2)
    cache.remove("x")
    assert cache.try_get("x") is None
    cache.put("z", 3)
    assert cache.try_get("y") == 2
    assert cache.try_get("z") == 3


if __name__ == "__main__":
    test_lru_example_from_assignment()
    test_remove_and_upsert()
    print("ok")
