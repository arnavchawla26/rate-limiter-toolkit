"""Load-test simulator: fires concurrent requests at a rate limiter and
reports throughput, rejection rate, and latency statistics.

This is deliberately independent of the HTTP middleware — it drives
:class:`~ratelimiter.base.RateLimiter` instances directly with a thread pool,
so it can be used to compare algorithms head-to-head without any network
overhead getting in the way of the numbers.
"""

from __future__ import annotations

import csv
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .base import RateLimiter


@dataclass
class SimulationResult:
    """Aggregated results of one simulation run against one limiter."""

    name: str
    total_requests: int
    allowed: int
    rejected: int
    duration_seconds: float
    latencies_ms: list[float] = field(default_factory=list, repr=False)

    @property
    def rejection_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.rejected / self.total_requests

    @property
    def throughput_per_second(self) -> float:
        if self.duration_seconds <= 0:
            return 0.0
        return self.allowed / self.duration_seconds

    @property
    def mean_latency_ms(self) -> float:
        return statistics.fmean(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def p50_latency_ms(self) -> float:
        return _percentile(self.latencies_ms, 50)

    @property
    def p99_latency_ms(self) -> float:
        return _percentile(self.latencies_ms, 99)

    def as_row(self) -> dict[str, object]:
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "allowed": self.allowed,
            "rejected": self.rejected,
            "rejection_rate": round(self.rejection_rate, 4),
            "throughput_per_second": round(self.throughput_per_second, 2),
            "mean_latency_ms": round(self.mean_latency_ms, 4),
            "p50_latency_ms": round(self.p50_latency_ms, 4),
            "p99_latency_ms": round(self.p99_latency_ms, 4),
        }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def simulate(
    limiter: RateLimiter,
    *,
    name: str,
    num_requests: int = 1000,
    concurrency: int = 50,
) -> SimulationResult:
    """Fire ``num_requests`` concurrent calls to ``limiter.check()`` using a
    thread pool of ``concurrency`` workers, and return aggregated stats.

    Latency here measures the wall-clock cost of the admission check itself
    (lock contention plus algorithm bookkeeping), not any downstream work —
    it's a proxy for how much overhead the limiter adds under contention.
    """
    latencies: list[float] = []
    allowed = 0
    rejected = 0

    def _one_request() -> tuple[bool, float]:
        start = time.perf_counter()
        decision = limiter.check()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return decision.allowed, elapsed_ms

    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for was_allowed, elapsed_ms in pool.map(lambda _: _one_request(), range(num_requests)):
            latencies.append(elapsed_ms)
            if was_allowed:
                allowed += 1
            else:
                rejected += 1
    duration = time.perf_counter() - start_time

    return SimulationResult(
        name=name,
        total_requests=num_requests,
        allowed=allowed,
        rejected=rejected,
        duration_seconds=duration,
        latencies_ms=latencies,
    )


def run_comparison(
    limiters: dict[str, RateLimiter],
    *,
    num_requests: int = 1000,
    concurrency: int = 50,
) -> list[SimulationResult]:
    """Run :func:`simulate` against each named limiter and return results in
    the same order the limiters were given."""
    return [
        simulate(limiter, name=name, num_requests=num_requests, concurrency=concurrency)
        for name, limiter in limiters.items()
    ]


def write_csv(results: list[SimulationResult], path: str | Path) -> None:
    """Write a comparison table of results to a CSV file."""
    path = Path(path)
    fieldnames = [
        "name",
        "total_requests",
        "allowed",
        "rejected",
        "rejection_rate",
        "throughput_per_second",
        "mean_latency_ms",
        "p50_latency_ms",
        "p99_latency_ms",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(result.as_row())


def format_summary_table(results: list[SimulationResult]) -> str:
    """Render a plain-text summary table, one row per limiter."""
    headers = ["name", "allowed", "rejected", "rej_rate", "req/s", "p50_ms", "p99_ms"]
    rows = []
    for r in results:
        rows.append(
            [
                r.name,
                str(r.allowed),
                str(r.rejected),
                f"{r.rejection_rate:.2%}",
                f"{r.throughput_per_second:.1f}",
                f"{r.p50_latency_ms:.3f}",
                f"{r.p99_latency_ms:.3f}",
            ]
        )
    widths = [max(len(h), *(len(row[i]) for row in rows)) if rows else len(h) for i, h in enumerate(headers)]
    lines = []
    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    lines.append(header_line)
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)
