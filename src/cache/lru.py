"""Least-recently-used cache (lesson 5, part 1)."""

from collections import OrderedDict
from typing import Any


class LeastRecentlyUsedCache:
    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be a positive integer")

        self._capacity = capacity
        self._items: OrderedDict[str, Any] = OrderedDict()

    def put(self, key: str, value: Any) -> None:
        if not key:
            raise ValueError("key must be a non-empty string")
        if value is None:
            raise ValueError("value must not be null")

        if key in self._items:
            self._items.move_to_end(key)

        self._items[key] = value

        if len(self._items) > self._capacity:
            self._items.popitem(last=False)

    def try_get(self, key: str) -> Any | None:
        if key not in self._items:
            return None

        self._items.move_to_end(key)
        return self._items[key]

    def remove(self, key: str) -> None:
        self._items.pop(key, None)

    def clear(self) -> None:
        self._items.clear()
