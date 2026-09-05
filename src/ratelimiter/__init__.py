"""rate-limiter-toolkit: dependency-free implementations of standard rate-limiting algorithms.

Exposes four classic algorithms behind a common interface:

    - TokenBucket
    - LeakyBucket
    - FixedWindowCounter
    - SlidingWindowLog
    - SlidingWindowCounter

All classes are thread-safe and depend only on the Python standard library.
"""

from .token_bucket import TokenBucket
from .leaky_bucket import LeakyBucket
from .fixed_window import FixedWindowCounter
from .sliding_window_log import SlidingWindowLog
from .sliding_window_counter import SlidingWindowCounter
from .base import RateLimiter

__all__ = [
    "RateLimiter",
    "TokenBucket",
    "LeakyBucket",
    "FixedWindowCounter",
    "SlidingWindowLog",
    "SlidingWindowCounter",
]

__version__ = "0.1.0"
