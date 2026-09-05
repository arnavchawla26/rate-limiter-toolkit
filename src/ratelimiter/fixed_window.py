"""Fixed-window counter rate limiter.

Time is divided into fixed-size windows (e.g. 1-second or 1-minute buckets)
aligned to an epoch. Each window has an independent counter; a request is
allowed as long as the counter for the current window hasn't reached the
limit. Simple and cheap, but allows up to 2x the limit's worth of traffic
across a window boundary (a burst at the end of one window plus a burst at
the start of the next).
"""

from __future__ import annotations

import math
import threading

from .base import Decision, RateLimiter


class FixedWindowCounter(RateLimiter):
    """Fixed-window counter limiter.

    Args:
        limit: Maximum number of requests (in cost units) allowed per window.
        window_seconds: Width of each window, in seconds.
    """

    def __init__(self, limit: float, window_seconds: float) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        super().__init__()
        self.limit = float(limit)
        self.window_seconds = float(window_seconds)
        self._window_index: int | None = None
        self._count = 0.0
        self._lock = threading.Lock()

    def _current_window(self, now: float) -> int:
        return math.floor(now / self.window_seconds)

    def _try_acquire(self, cost: float, now: float) -> Decision:
        with self._lock:
            window = self._current_window(now)
            if self._window_index != window:
                self._window_index = window
                self._count = 0.0
            if self._count + cost <= self.limit:
                self._count += cost
                return Decision(allowed=True)
            window_end = (window + 1) * self.window_seconds
            return Decision(allowed=False, retry_after=max(0.0, window_end - now))

    @property
    def current_count(self) -> float:
        with self._lock:
            return self._count
