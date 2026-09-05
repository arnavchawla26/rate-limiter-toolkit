import pytest

from ratelimiter import TokenBucket


def test_allows_up_to_capacity_burst():
    bucket = TokenBucket(capacity=5, refill_rate=1)
    for _ in range(5):
        assert bucket.allow(now=0.0) is True
    assert bucket.allow(now=0.0) is False


def test_refills_over_time():
    bucket = TokenBucket(capacity=5, refill_rate=2)  # 2 tokens/sec
    for _ in range(5):
        assert bucket.allow(now=0.0) is True
    assert bucket.allow(now=0.0) is False
    # 0.5s later, 1 token should have refilled.
    assert bucket.allow(now=0.5) is True
    assert bucket.allow(now=0.5) is False


def test_never_exceeds_capacity():
    bucket = TokenBucket(capacity=3, refill_rate=100)
    bucket.allow(now=0.0)
    # A huge amount of elapsed time shouldn't overfill past capacity.
    assert bucket.available_tokens <= 3
    assert bucket.allow(now=1000.0) is True
    assert bucket.available_tokens <= 3


def test_retry_after_is_positive_when_rejected():
    bucket = TokenBucket(capacity=1, refill_rate=1)
    assert bucket.allow(now=0.0) is True
    decision = bucket.check(now=0.0)
    assert decision.allowed is False
    assert decision.retry_after > 0


def test_variable_cost_requests():
    bucket = TokenBucket(capacity=10, refill_rate=1)
    assert bucket.allow(cost=7, now=0.0) is True
    assert bucket.allow(cost=4, now=0.0) is False
    assert bucket.allow(cost=3, now=0.0) is True


def test_rejects_invalid_construction():
    with pytest.raises(ValueError):
        TokenBucket(capacity=0, refill_rate=1)
    with pytest.raises(ValueError):
        TokenBucket(capacity=1, refill_rate=0)


def test_rejects_non_positive_cost():
    bucket = TokenBucket(capacity=1, refill_rate=1)
    with pytest.raises(ValueError):
        bucket.allow(cost=0, now=0.0)
    with pytest.raises(ValueError):
        bucket.allow(cost=-1, now=0.0)


def test_stats_track_allowed_and_rejected():
    bucket = TokenBucket(capacity=2, refill_rate=1)
    bucket.allow(now=0.0)
    bucket.allow(now=0.0)
    bucket.allow(now=0.0)
    assert bucket.stats.allowed == 2
    assert bucket.stats.rejected == 1
    assert bucket.stats.total == 3
    assert bucket.stats.rejection_rate == pytest.approx(1 / 3)


def test_concurrent_access_never_oversells_tokens():
    import threading

    bucket = TokenBucket(capacity=100, refill_rate=0.0001)
    allowed_count = 0
    lock = threading.Lock()

    def worker():
        nonlocal allowed_count
        if bucket.allow(now=0.0):
            with lock:
                allowed_count += 1

    threads = [threading.Thread(target=worker) for _ in range(500)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert allowed_count == 100
