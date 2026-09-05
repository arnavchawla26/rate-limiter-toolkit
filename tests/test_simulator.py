import csv

from ratelimiter import TokenBucket, FixedWindowCounter
from ratelimiter.simulator import (
    simulate,
    run_comparison,
    write_csv,
    format_summary_table,
    _percentile,
)


def test_simulate_reports_correct_totals():
    limiter = TokenBucket(capacity=1_000_000, refill_rate=1)
    result = simulate(limiter, name="token_bucket", num_requests=200, concurrency=10)
    assert result.total_requests == 200
    assert result.allowed == 200
    assert result.rejected == 0
    assert result.rejection_rate == 0.0
    assert len(result.latencies_ms) == 200


def test_simulate_captures_rejections_under_a_tight_limit():
    limiter = TokenBucket(capacity=5, refill_rate=0.00001)
    result = simulate(limiter, name="tight", num_requests=100, concurrency=20)
    assert result.allowed == 5
    assert result.rejected == 95
    assert result.rejection_rate == 0.95


def test_run_comparison_preserves_order_and_names():
    limiters = {
        "token_bucket": TokenBucket(capacity=10, refill_rate=1000),
        "fixed_window": FixedWindowCounter(limit=10, window_seconds=1),
    }
    results = run_comparison(limiters, num_requests=50, concurrency=5)
    assert [r.name for r in results] == ["token_bucket", "fixed_window"]


def test_write_csv_round_trips_rows(tmp_path):
    limiter = TokenBucket(capacity=1_000_000, refill_rate=1)
    result = simulate(limiter, name="csv_test", num_requests=30, concurrency=3)
    out_path = tmp_path / "results.csv"
    write_csv([result], out_path)

    with out_path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["name"] == "csv_test"
    assert int(rows[0]["allowed"]) == 30


def test_format_summary_table_contains_all_names():
    limiters = {
        "a": TokenBucket(capacity=5, refill_rate=1000),
        "b": FixedWindowCounter(limit=5, window_seconds=1),
    }
    results = run_comparison(limiters, num_requests=20, concurrency=4)
    table = format_summary_table(results)
    assert "a" in table
    assert "b" in table
    assert "req/s" in table


def test_percentile_helper_handles_edge_cases():
    assert _percentile([], 50) == 0.0
    assert _percentile([5.0], 99) == 5.0
    assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == 3.0
