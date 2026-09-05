"""Example: same limiter, two traffic shapes.

Demonstrates why the `compare_algorithms.py` example shows ~95% rejection:
firing thousands of requests as fast as possible in a fraction of a second
is a massive burst relative to a "100 requests/second" budget. This script
contrasts that burst against *paced* traffic that actually arrives at (or
under) the configured rate, where rejection should be near zero.

Run with:

    python examples/sustained_vs_burst.py
"""

import time

from ratelimiter import TokenBucket

LIMIT = 20
WINDOW_SECONDS = 1.0
RATE = LIMIT / WINDOW_SECONDS


def run_burst() -> None:
    bucket = TokenBucket(capacity=LIMIT, refill_rate=RATE)
    allowed = sum(1 for _ in range(200) if bucket.allow())
    print(f"Burst (200 requests fired instantly):   {allowed}/200 allowed "
          f"({allowed / 200:.1%})")


def run_paced() -> None:
    bucket = TokenBucket(capacity=LIMIT, refill_rate=RATE)
    total = 40
    allowed = 0
    interval = 1.0 / RATE  # space requests out to match the refill rate
    for _ in range(total):
        if bucket.allow():
            allowed += 1
        time.sleep(interval)
    print(f"Paced ({total} requests at the limiter's own rate): {allowed}/{total} allowed "
          f"({allowed / total:.1%})")


if __name__ == "__main__":
    run_burst()
    run_paced()
