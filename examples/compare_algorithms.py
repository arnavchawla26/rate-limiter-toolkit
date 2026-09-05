"""Example: compare all five rate-limiting algorithms head-to-head.

Run with:

    python examples/compare_algorithms.py

Equivalent to the CLI's `ratelimit-sim compare` subcommand, but shown here
as plain library calls so you can see exactly how the pieces fit together.
"""

from ratelimiter import (
    FixedWindowCounter,
    LeakyBucket,
    SlidingWindowCounter,
    SlidingWindowLog,
    TokenBucket,
)
from ratelimiter.simulator import format_summary_table, run_comparison

LIMIT = 100
WINDOW_SECONDS = 1.0
RATE = LIMIT / WINDOW_SECONDS

limiters = {
    "token_bucket": TokenBucket(capacity=LIMIT, refill_rate=RATE),
    "leaky_bucket": LeakyBucket(capacity=LIMIT, leak_rate=RATE),
    "fixed_window": FixedWindowCounter(limit=LIMIT, window_seconds=WINDOW_SECONDS),
    "sliding_log": SlidingWindowLog(limit=LIMIT, window_seconds=WINDOW_SECONDS),
    "sliding_counter": SlidingWindowCounter(limit=LIMIT, window_seconds=WINDOW_SECONDS),
}

if __name__ == "__main__":
    results = run_comparison(limiters, num_requests=2000, concurrency=50)
    print(format_summary_table(results))
