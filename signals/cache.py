"""Tiny in-process TTL cache so we don't hammer public APIs."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def get_or_set(key: str, ttl_s: float, loader: Callable[[], T]) -> T:
    now = time.time()
    with _lock:
        hit = _store.get(key)
        if hit and now - hit[0] < ttl_s:
            return hit[1]
    value = loader()
    with _lock:
        _store[key] = (time.time(), value)
    return value


def clear() -> None:
    with _lock:
        _store.clear()
