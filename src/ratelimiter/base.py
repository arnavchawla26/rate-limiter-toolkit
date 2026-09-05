"""Common interface shared by every rate limiter in this package."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Decision:
    """The result of asking a rate limiter whether to allow a request.

    Attributes:
        allowed: Whether the request should proceed.
        retry_after: Seconds the caller should wait before retrying, when
            ``allowed`` is False. ``0.0`` when the retry time is unknown or
            not applicable (e.g. the request was allowed).
    """

    allowed: bool
    retry_after: float = 0.0


@dataclass
class LimiterStats:
    """Running counters every limiter maintains for introspection/reporting."""

    allowed: int = 0
    rejected: int = 0

    @property
    def total(self) -> int:
        return self.allowed + self.rejected

    @property
    def rejection_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.rejected / self.total


class RateLimiter(ABC):
    """Abstract base class every rate-limiting algorithm implements.

    Subclasses must be safe to call concurrently from multiple threads;
    each implementation guards its internal state with a ``threading.Lock``.
    """

    def __init__(self) -> None:
        self.stats = LimiterStats()

    @abstractmethod
    def _try_acquire(self, cost: float, now: float) -> Decision:
        """Algorithm-specific admission logic. Must be called under a lock."""
        raise NotImplementedError

    def allow(self, cost: float = 1.0, now: float | None = None) -> bool:
        """Return True if a request of the given ``cost`` should be allowed."""
        return self.check(cost=cost, now=now).allowed

    def check(self, cost: float = 1.0, now: float | None = None) -> Decision:
        """Return a full :class:`Decision`, including a retry-after hint."""
        if cost <= 0:
            raise ValueError("cost must be positive")
        ts = time.monotonic() if now is None else now
        decision = self._try_acquire(cost, ts)
        if decision.allowed:
            self.stats.allowed += 1
        else:
            self.stats.rejected += 1
        return decision

    def reset_stats(self) -> None:
        self.stats = LimiterStats()
