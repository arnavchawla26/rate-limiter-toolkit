"""Leaky bucket rate limiter (as a queue / metering variant).

Requests fill a fixed-capacity bucket; the bucket "leaks" (processes) at a
constant rate regardless of arrival pattern. This smooths bursty traffic
into a steady output rate rather than allowing bursts through, which is the
main behavioral difference from the token bucket.
"""

from __future__ import annotations

import threading

from .base import Decision, RateLimiter


class LeakyBucket(RateLimiter):
    """Leaky-bucket-as-a-meter limiter.

    Args:
        capacity: Maximum queued "work" the bucket can hold before it
            overflows (rejects new requests).
        leak_rate: Units of work drained from the bucket per second.
    """

    def __init__(self, capacity: float, leak_rate: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if leak_rate <= 0:
            raise ValueError("leak_rate must be positive")
        super().__init__()
        self.capacity = float(capacity)
        self.leak_rate = float(leak_rate)
        self._level = 0.0
        self._last_leak: float | None = None
        self._lock = threading.Lock()

    def _leak(self, now: float) -> None:
        if self._last_leak is None:
            self._last_leak = now
            return
        elapsed = now - self._last_leak
        if elapsed <= 0:
            return
        self._level = max(0.0, self._level - elapsed * self.leak_rate)
        self._last_leak = now

    def _try_acquire(self, cost: float, now: float) -> Decision:
        with self._lock:
            self._leak(now)
            if self._level + cost <= self.capacity:
                self._level += cost
                return Decision(allowed=True)
            overflow = self._level + cost - self.capacity
            retry_after = overflow / self.leak_rate
            return Decision(allowed=False, retry_after=retry_after)

    @property
    def level(self) -> float:
        """Snapshot of the current bucket fill level."""
        with self._lock:
            return self._level
