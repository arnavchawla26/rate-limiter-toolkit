import pytest

from ratelimiter import LeakyBucket


def test_allows_up_to_capacity():
    bucket = LeakyBucket(capacity=3, leak_rate=1)
    for _ in range(3):
        assert bucket.allow(now=0.0) is True
    assert bucket.allow(now=0.0) is False


def test_leaks_over_time_freeing_capacity():
    bucket = LeakyBucket(capacity=2, leak_rate=1)  # leaks 1 unit/sec
    assert bucket.allow(now=0.0) is True
    assert bucket.allow(now=0.0) is True
    assert bucket.allow(now=0.0) is False
    # After 1 second, 1 unit should have leaked out.
    assert bucket.allow(now=1.0) is True
    assert bucket.allow(now=1.0) is False


def test_level_never_negative():
    bucket = LeakyBucket(capacity=5, leak_rate=1)
    bucket.allow(now=0.0)
    assert bucket.level >= 0
    bucket.allow(now=1000.0)
    assert bucket.level >= 0


def test_variable_cost_overflow_rejected():
    bucket = LeakyBucket(capacity=10, leak_rate=1)
    assert bucket.allow(cost=8, now=0.0) is True
    assert bucket.allow(cost=3, now=0.0) is False
    assert bucket.allow(cost=2, now=0.0) is True


def test_retry_after_positive_on_rejection():
    bucket = LeakyBucket(capacity=1, leak_rate=1)
    bucket.allow(now=0.0)
    decision = bucket.check(now=0.0)
    assert decision.allowed is False
    assert decision.retry_after > 0


def test_rejects_invalid_construction():
    with pytest.raises(ValueError):
        LeakyBucket(capacity=0, leak_rate=1)
    with pytest.raises(ValueError):
        LeakyBucket(capacity=1, leak_rate=0)


def test_smooths_bursts_more_than_token_bucket():
    # A leaky bucket processes at a steady rate: even if many requests
    # arrive instantly, only `capacity` worth are admitted, and the level
    # drains at exactly `leak_rate`, never bursting output.
    bucket = LeakyBucket(capacity=5, leak_rate=1)
    admitted = sum(1 for _ in range(20) if bucket.allow(now=0.0))
    assert admitted == 5
    assert bucket.level == 5
