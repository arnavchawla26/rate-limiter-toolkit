"""Sliding-window counter rate limiter.

Approximates the sliding-window log using O(1) memory: it keeps two fixed
window counters (previous and current) and estimates the trailing-window
count as a weighted blend of them, weighted by how far the current instant
is into the current window. This avoids the fixed window's boundary-burst
problem almost entirely, at the cost of being an approximation rather than
an exact count.
"""

from __future__ import annotations

import math
import threading

from .base import Decision, RateLimiter


class SlidingWindowCounter(RateLimiter):
    """Approximate sliding-window limiter using two rolling fixed windows.

    Args:
        limit: Maximum (weighted) requests allowed in any trailing window.
        window_seconds: Width of each underlying fixed window, in seconds.
    """

    def __init__(self, limit: float, window_seconds: float) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        super().__init__()
        self.limit = float(limit)
        self.window_seconds = float(window_seconds)
        self._current_index: int | None = None
        self._current_count = 0.0
        self._previous_count = 0.0
        self._last_estimate = 0.0
        self._lock = threading.Lock()

    def _roll(self, now: float) -> float:
        """Advance the window state to ``now`` and return the elapsed
        fraction of the current window (0.0 at the window's start, close to
        1.0 near its end)."""
        window = math.floor(now / self.window_seconds)
        if self._current_index is None:
            self._current_index = window
        elif window == self._current_index + 1:
            self._previous_count = self._current_count
            self._current_count = 0.0
            self._current_index = window
        elif window > self._current_index + 1:
            # More than one full window elapsed with no traffic: both
            # windows are stale.
            self._previous_count = 0.0
            self._current_count = 0.0
            self._current_index = window
        elapsed_in_window = now - window * self.window_seconds
        return elapsed_in_window / self.window_seconds

    def _try_acquire(self, cost: float, now: float) -> Decision:
        with self._lock:
            fraction_elapsed = self._roll(now)
            weighted_previous = self._previous_count * (1.0 - fraction_elapsed)
            estimated_count = weighted_previous + self._current_count
            self._last_estimate = estimated_count
            if estimated_count + cost <= self.limit:
                self._current_count += cost
                self._last_estimate = estimated_count + cost
                return Decision(allowed=True)
            # Rough retry-after estimate: time until the weighted estimate
            # decays (via the previous window's shrinking weight) enough to
            # admit one more unit of cost. Falls back to the window width
            # when the previous window no longer contributes.
            if self._previous_count > 0:
                # weighted_previous decays linearly to 0 over the rest of
                # the current window; solve for when estimated_count drops
                # by the overflow amount.
                overflow = estimated_count + cost - self.limit
                remaining_in_window = self.window_seconds * (1.0 - fraction_elapsed)
                decay_rate = self._previous_count / self.window_seconds
                if decay_rate > 0:
                    retry_after = min(remaining_in_window, overflow / decay_rate)
                else:
                    retry_after = remaining_in_window
            else:
                retry_after = self.window_seconds * (1.0 - fraction_elapsed)
            return Decision(allowed=False, retry_after=max(0.0, retry_after))

    @property
    def estimated_count(self) -> float:
        """Weighted estimate as of the most recent :meth:`check` call.

        This is a snapshot from the last admission check, not a live
        recomputation — the estimate only changes when ``now`` advances,
        which requires a call to ``check``/``allow``.
        """
        with self._lock:
            return self._last_estimate
