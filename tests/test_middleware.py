import json
import urllib.request
import urllib.error

import pytest

from ratelimiter import TokenBucket
from ratelimiter.middleware import RateLimitedHTTPServer, serve_forever_in_thread


@pytest.fixture()
def server():
    srv = RateLimitedHTTPServer(
        ("127.0.0.1", 0),
        limiter_factory=lambda: TokenBucket(capacity=2, refill_rate=0.0001),
    )
    thread = serve_forever_in_thread(srv)
    yield srv
    srv.shutdown()
    thread.join(timeout=2)


def _get(port: int, client_id: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}/", headers={"X-Client-Id": client_id})
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_allows_requests_under_capacity(server):
    port = server.server_address[1]
    status, body = _get(port, "alice")
    assert status == 200
    assert body["status"] == "ok"
    assert body["client"] == "alice"


def test_rejects_requests_over_capacity(server):
    port = server.server_address[1]
    _get(port, "bob")
    _get(port, "bob")
    status, body = _get(port, "bob")
    assert status == 429
    assert body["status"] == "rate_limited"
    assert body["retry_after"] > 0


def test_clients_are_isolated(server):
    port = server.server_address[1]
    _get(port, "carol")
    _get(port, "carol")
    # carol is now exhausted, but dave has a fresh bucket.
    status, _ = _get(port, "carol")
    assert status == 429
    status, body = _get(port, "dave")
    assert status == 200
    assert body["client"] == "dave"


def test_stats_snapshot_tracks_per_client_counts(server):
    port = server.server_address[1]
    _get(port, "eve")
    _get(port, "eve")
    _get(port, "eve")  # rejected
    stats = server.snapshot_stats()
    assert stats["eve"]["allowed"] == 2
    assert stats["eve"]["rejected"] == 1


def test_falls_back_to_client_ip_without_header():
    srv = RateLimitedHTTPServer(
        ("127.0.0.1", 0),
        limiter_factory=lambda: TokenBucket(capacity=5, refill_rate=1),
    )
    thread = serve_forever_in_thread(srv)
    try:
        port = srv.server_address[1]
        req = urllib.request.Request(f"http://127.0.0.1:{port}/")
        with urllib.request.urlopen(req, timeout=2) as resp:
            body = json.loads(resp.read())
        assert body["client"] == "127.0.0.1"
    finally:
        srv.shutdown()
        thread.join(timeout=2)
