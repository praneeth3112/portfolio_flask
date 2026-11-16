"""A small thread-safe sliding-window rate limiter."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable


class SlidingWindowLimiter:
    """Allow at most ``limit`` hits per ``window`` seconds for each key."""

    def __init__(self, limit: int, window: float = 3600.0,
                 clock: Callable[[], float] = time.monotonic):
        if limit < 1 or window <= 0:
            raise ValueError("limit must be >= 1 and window > 0")
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        return hits

    def allow(self, key: str) -> bool:
        """Record a hit and return True if it is within the limit."""
        with self._lock:
            now = self._clock()
            hits = self._prune(key, now)
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def retry_after(self, key: str) -> int:
        """Seconds until ``key`` may try again (0 if it can now)."""
        with self._lock:
            now = self._clock()
            hits = self._prune(key, now)
            if len(hits) < self.limit:
                return 0
            return max(1, int(self.window - (now - hits[0])) + 1)
