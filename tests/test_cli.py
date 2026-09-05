import subprocess
import sys
import csv


def _run(args, **kwargs):
    return subprocess.run(
        [sys.executable, "-m", "ratelimiter.cli", *args],
        capture_output=True,
        text=True,
        timeout=30,
        **kwargs,
    )


def test_compare_runs_and_prints_all_algorithms():
    result = _run(["compare", "--requests", "200", "--concurrency", "10", "--limit", "20", "--window", "1"])
    assert result.returncode == 0
    for name in ("token_bucket", "leaky_bucket", "fixed_window", "sliding_log", "sliding_counter"):
        assert name in result.stdout


def test_compare_writes_csv(tmp_path):
    out_csv = tmp_path / "out.csv"
    result = _run(
        [
            "compare",
            "--requests",
            "100",
            "--concurrency",
            "5",
            "--limit",
            "10",
            "--window",
            "1",
            "--csv",
            str(out_csv),
        ]
    )
    assert result.returncode == 0
    assert out_csv.exists()
    with out_csv.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 5


def test_build_limiter_dispatches_all_algorithms():
    from ratelimiter.cli import _build_limiter, ALGORITHMS

    for name in ALGORITHMS:
        limiter = _build_limiter(name, limit=10, window_seconds=1)
        assert limiter.allow(now=0.0) in (True, False)


def test_no_command_shows_usage_error():
    result = _run([])
    assert result.returncode != 0
