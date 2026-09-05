import pytest

from ratelimiter import SlidingWindowLog


def test_allows_up_to_limit():
    limiter = SlidingWindowLog(limit=3, window_seconds=1)
    for _ in range(3):
        assert limiter.allow(now=0.0) is True
    assert limiter.allow(now=0.0) is False


def test_no_boundary_burst_unlike_fixed_window():
    # Unlike the fixed window, requests near a would-be boundary are
    # limited relative to the trailing window, not a fixed clock-aligned one.
    limiter = SlidingWindowLog(limit=5, window_seconds=1)
    for _ in range(5):
        assert limiter.allow(now=0.99) is True
    # Still within 1 second of the earlier requests -> rejected.
    assert limiter.allow(now=1.01) is False
    # Once the earliest entries age out of the window, new ones are allowed.
    assert limiter.allow(now=2.0) is True


def test_old_entries_are_evicted():
    limiter = SlidingWindowLog(limit=2, window_seconds=1)
    assert limiter.allow(now=0.0) is True
    assert limiter.allow(now=0.0) is True
    assert limiter.allow(now=0.5) is False
    assert limiter.current_count == 2
    assert limiter.allow(now=1.5) is True  # both entries aged out
    assert limiter.current_count == 1


def test_retry_after_reflects_oldest_entry_expiry():
    limiter = SlidingWindowLog(limit=1, window_seconds=2)
    limiter.allow(now=0.0)
    decision = limiter.check(now=1.0)
    assert decision.allowed is False
    assert decision.retry_after == pytest.approx(1.0)


def test_rejects_invalid_construction():
    with pytest.raises(ValueError):
        SlidingWindowLog(limit=0, window_seconds=1)
    with pytest.raises(ValueError):
        SlidingWindowLog(limit=1, window_seconds=0)


def test_multi_slot_cost_rounds_up():
    limiter = SlidingWindowLog(limit=5, window_seconds=1)
    assert limiter.allow(cost=2, now=0.0) is True
    assert limiter.current_count == 2
    assert limiter.allow(cost=2.5, now=0.0) is True
    assert limiter.current_count == 5
    assert limiter.allow(cost=1, now=0.0) is False
