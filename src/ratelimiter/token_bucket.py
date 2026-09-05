"""Token bucket rate limiter.

Tokens accumulate in a bucket at a constant fill rate, up to a maximum
capacity. Each request consumes one or more tokens; if there aren't enough
tokens available, the request is rejected. This algorithm allows short
bursts up to the bucket's capacity while enforcing a long-run average rate.
"""

from __future__ import annotations

import threading

from .base import Decision, RateLimiter


class TokenBucket(RateLimiter):
    """Classic token-bucket limiter.

    Args:
        capacity: Maximum number of tokens the bucket can hold (burst size).
        refill_rate: Tokens added per second.
        initial_tokens: Starting token count. Defaults to a full bucket.
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        initial_tokens: float | None = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
        super().__init__()
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._tokens = self.capacity if initial_tokens is None else float(initial_tokens)
        self._last_refill: float | None = None
        self._lock = threading.Lock()

    def _refill(self, now: float) -> None:
        if self._last_refill is None:
            self._last_refill = now
            return
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now

    def _try_acquire(self, cost: float, now: float) -> Decision:
        with self._lock:
            self._refill(now)
            if self._tokens >= cost:
                self._tokens -= cost
                return Decision(allowed=True)
            missing = cost - self._tokens
            retry_after = missing / self.refill_rate
            return Decision(allowed=False, retry_after=retry_after)

    @property
    def available_tokens(self) -> float:
        """Snapshot of the current token count (refills as of the last check)."""
        with self._lock:
            return self._tokens
