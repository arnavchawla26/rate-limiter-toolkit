"""``ratelimit-sim`` command-line interface.

Subcommands:
    compare   Run the load-test simulator across all five algorithms and
              print a summary table (optionally writing a CSV).
    serve     Start the demo rate-limited HTTP server on a given algorithm.
"""

from __future__ import annotations

import argparse
import sys

from .base import RateLimiter
from .fixed_window import FixedWindowCounter
from .leaky_bucket import LeakyBucket
from .middleware import RateLimitedHTTPServer, serve_forever_in_thread
from .simulator import format_summary_table, run_comparison, write_csv
from .sliding_window_counter import SlidingWindowCounter
from .sliding_window_log import SlidingWindowLog
from .token_bucket import TokenBucket

ALGORITHMS = ("token_bucket", "leaky_bucket", "fixed_window", "sliding_log", "sliding_counter")


def _build_limiter(algorithm: str, *, limit: float, window_seconds: float) -> RateLimiter:
    rate = limit / window_seconds
    if algorithm == "token_bucket":
        return TokenBucket(capacity=limit, refill_rate=rate)
    if algorithm == "leaky_bucket":
        return LeakyBucket(capacity=limit, leak_rate=rate)
    if algorithm == "fixed_window":
        return FixedWindowCounter(limit=limit, window_seconds=window_seconds)
    if algorithm == "sliding_log":
        return SlidingWindowLog(limit=int(limit), window_seconds=window_seconds)
    if algorithm == "sliding_counter":
        return SlidingWindowCounter(limit=limit, window_seconds=window_seconds)
    raise ValueError(f"unknown algorithm: {algorithm}")


def _cmd_compare(args: argparse.Namespace) -> int:
    limiters = {
        name: _build_limiter(name, limit=args.limit, window_seconds=args.window)
        for name in ALGORITHMS
    }
    results = run_comparison(limiters, num_requests=args.requests, concurrency=args.concurrency)
    print(
        f"Simulating {args.requests} requests at concurrency={args.concurrency} "
        f"against a limit of {args.limit} per {args.window}s window...\n"
    )
    print(format_summary_table(results))
    if args.csv:
        write_csv(results, args.csv)
        print(f"\nWrote {args.csv}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    limiter_factory = lambda: _build_limiter(args.algorithm, limit=args.limit, window_seconds=args.window)  # noqa: E731
    server = RateLimitedHTTPServer(("127.0.0.1", args.port), limiter_factory=limiter_factory)
    port = server.server_address[1]
    print(f"Serving on http://127.0.0.1:{port} using '{args.algorithm}' "
          f"(limit={args.limit} per {args.window}s). Press Ctrl+C to stop.")
    thread = serve_forever_in_thread(server)
    try:
        thread.join()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ratelimit-sim", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare = subparsers.add_parser("compare", help="Load-test all algorithms and compare results.")
    compare.add_argument("--requests", type=int, default=2000, help="Total requests to fire (default: 2000).")
    compare.add_argument("--concurrency", type=int, default=50, help="Concurrent worker threads (default: 50).")
    compare.add_argument("--limit", type=float, default=100.0, help="Requests allowed per window (default: 100).")
    compare.add_argument("--window", type=float, default=1.0, help="Window size in seconds (default: 1.0).")
    compare.add_argument("--csv", type=str, default=None, help="Optional path to write a CSV of results.")
    compare.set_defaults(func=_cmd_compare)

    serve = subparsers.add_parser("serve", help="Run the demo HTTP server with a chosen algorithm.")
    serve.add_argument("--algorithm", choices=ALGORITHMS, default="token_bucket")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--limit", type=float, default=10.0, help="Requests allowed per window (default: 10).")
    serve.add_argument("--window", type=float, default=1.0, help="Window size in seconds (default: 1.0).")
    serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
