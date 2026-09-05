"""Sliding-window log rate limiter.

Keeps a timestamp for every allowed request within the trailing window. A
new request is allowed only if fewer than ``limit`` timestamps remain after
discarding ones older than ``window_seconds``. This is exact (no boundary
burst problem like the fixed window) but costs O(limit) memory per key and
O(limit) work per check in the worst case.
"""

from __future__ import annotations

import threading
from collections import deque

from .base import Decision, RateLimiter


class SlidingWindowLog(RateLimiter):
    """Exact sliding-window limiter backed by a log of request timestamps.

    Args:
        limit: Maximum number of requests allowed in any trailing window.
        window_seconds: Width of the trailing window, in seconds.
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        super().__init__()
        self.limit = int(limit)
        self.window_seconds = float(window_seconds)
        self._log: deque[float] = deque()
        self._lock = threading.Lock()

    def _evict(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._log and self._log[0] <= cutoff:
            self._log.popleft()

    def _try_acquire(self, cost: float, now: float) -> Decision:
        # Each unit of cost occupies one log slot; fractional cost isn't
        # meaningful for a log-based limiter, so it's rounded up.
        slots = max(1, int(cost + 0.999999))
        with self._lock:
            self._evict(now)
            if len(self._log) + slots <= self.limit:
                for _ in range(slots):
                    self._log.append(now)
                return Decision(allowed=True)
            # Retry-after: when the oldest entry ages out of the window.
            if self._log:
                retry_after = max(0.0, self._log[0] + self.window_seconds - now)
            else:
                retry_after = 0.0
            return Decision(allowed=False, retry_after=retry_after)

    @property
    def current_count(self) -> int:
        with self._lock:
            return len(self._log)
