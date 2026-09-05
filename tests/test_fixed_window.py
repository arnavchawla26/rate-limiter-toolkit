import pytest

from ratelimiter import FixedWindowCounter


def test_allows_up_to_limit_within_window():
    limiter = FixedWindowCounter(limit=3, window_seconds=1)
    for _ in range(3):
        assert limiter.allow(now=0.1) is True
    assert limiter.allow(now=0.2) is False


def test_resets_on_new_window():
    limiter = FixedWindowCounter(limit=2, window_seconds=1)
    assert limiter.allow(now=0.5) is True
    assert limiter.allow(now=0.5) is True
    assert limiter.allow(now=0.9) is False
    # New window starting at t=1.0
    assert limiter.allow(now=1.0) is True


def test_boundary_burst_is_a_known_property():
    # Demonstrates the fixed window's classic weakness: a burst at the end
    # of one window plus a burst at the start of the next can total up to
    # 2x the limit within a short span straddling the boundary.
    limiter = FixedWindowCounter(limit=5, window_seconds=1)
    allowed_near_end = sum(1 for _ in range(5) if limiter.allow(now=0.99))
    allowed_near_start = sum(1 for _ in range(5) if limiter.allow(now=1.01))
    assert allowed_near_end == 5
    assert allowed_near_start == 5


def test_retry_after_points_to_window_boundary():
    limiter = FixedWindowCounter(limit=1, window_seconds=2)
    limiter.allow(now=0.5)
    decision = limiter.check(now=0.5)
    assert decision.allowed is False
    assert decision.retry_after == pytest.approx(1.5)


def test_current_count_tracks_window():
    limiter = FixedWindowCounter(limit=10, window_seconds=1)
    limiter.allow(cost=4, now=0.1)
    assert limiter.current_count == 4
    limiter.allow(cost=1, now=1.5)  # new window
    assert limiter.current_count == 1


def test_rejects_invalid_construction():
    with pytest.raises(ValueError):
        FixedWindowCounter(limit=0, window_seconds=1)
    with pytest.raises(ValueError):
        FixedWindowCounter(limit=1, window_seconds=0)
