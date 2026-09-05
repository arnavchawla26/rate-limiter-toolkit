import pytest

from ratelimiter import SlidingWindowCounter


def test_allows_up_to_limit_within_first_window():
    limiter = SlidingWindowCounter(limit=3, window_seconds=1)
    for _ in range(3):
        assert limiter.allow(now=0.1) is True
    assert limiter.allow(now=0.2) is False


def test_smooths_boundary_better_than_fixed_window():
    # Fill the first window right at its end.
    limiter = SlidingWindowCounter(limit=5, window_seconds=1)
    for _ in range(5):
        assert limiter.allow(now=0.9) is True
    # Immediately after the boundary, the previous window's count is
    # still weighted in almost fully, so a full second burst is rejected
    # (unlike the fixed window, which would allow it).
    assert limiter.allow(now=1.0) is False


def test_previous_window_weight_decays_across_the_window():
    limiter = SlidingWindowCounter(limit=5, window_seconds=1)
    for _ in range(5):
        limiter.allow(now=0.99)
    # Near the very end of the next window, the previous window's weight
    # has decayed close to zero, so new requests should be admitted again.
    admitted = sum(1 for _ in range(5) if limiter.allow(now=1.98))
    assert admitted > 0


def test_multiple_empty_windows_reset_state():
    limiter = SlidingWindowCounter(limit=2, window_seconds=1)
    limiter.allow(now=0.0)
    limiter.allow(now=0.0)
    # Long gap with no traffic -> both windows should be considered stale.
    assert limiter.allow(now=100.0) is True


def test_rejects_invalid_construction():
    with pytest.raises(ValueError):
        SlidingWindowCounter(limit=0, window_seconds=1)
    with pytest.raises(ValueError):
        SlidingWindowCounter(limit=1, window_seconds=0)


def test_estimated_count_reflects_last_check():
    limiter = SlidingWindowCounter(limit=10, window_seconds=1)
    limiter.allow(cost=4, now=0.5)
    assert limiter.estimated_count == pytest.approx(4.0)
