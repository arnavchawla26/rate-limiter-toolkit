"""A small threaded HTTP server demonstrating rate limiting as middleware.

Wraps :mod:`http.server`'s stdlib primitives (no third-party web framework)
with a per-client-key rate limiter. Each client is identified by a header
(defaults to ``X-Client-Id``, falling back to the connecting IP address) and
gets its own limiter instance, so one noisy client can't starve another.

This is a demo/reference implementation, not a production-grade server:
it's meant to show how any :class:`~ratelimiter.base.RateLimiter` plugs into
a request-handling pipeline with a handful of lines of glue code.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from .base import RateLimiter

LimiterFactory = Callable[[], RateLimiter]


class RateLimitedHTTPServer(ThreadingHTTPServer):
    """A ``ThreadingHTTPServer`` that rate-limits requests per client key.

    Args:
        server_address: ``(host, port)`` tuple, as for ``HTTPServer``.
        limiter_factory: A zero-argument callable that constructs a fresh
            :class:`RateLimiter` for a new client key. Each key gets its own
            limiter instance, created lazily on first request.
        client_key_header: Request header used to identify the client.
            Falls back to the connecting address when absent.
    """

    def __init__(
        self,
        server_address: tuple[str, int],
        limiter_factory: LimiterFactory,
        client_key_header: str = "X-Client-Id",
    ) -> None:
        self.limiter_factory = limiter_factory
        self.client_key_header = client_key_header
        self._limiters: dict[str, RateLimiter] = {}
        self._limiters_lock = threading.Lock()
        super().__init__(server_address, _RateLimitedHandler)

    def limiter_for(self, client_key: str) -> RateLimiter:
        with self._limiters_lock:
            limiter = self._limiters.get(client_key)
            if limiter is None:
                limiter = self.limiter_factory()
                self._limiters[client_key] = limiter
            return limiter

    def snapshot_stats(self) -> dict[str, dict[str, int | float]]:
        """Return a per-client snapshot of allowed/rejected counts."""
        with self._limiters_lock:
            return {
                key: {
                    "allowed": limiter.stats.allowed,
                    "rejected": limiter.stats.rejected,
                    "rejection_rate": limiter.stats.rejection_rate,
                }
                for key, limiter in self._limiters.items()
            }


class _RateLimitedHandler(BaseHTTPRequestHandler):
    server: RateLimitedHTTPServer  # type: ignore[assignment]

    def _client_key(self) -> str:
        header_value = self.headers.get(self.server.client_key_header)
        if header_value:
            return header_value
        return self.client_address[0]

    def _handle(self) -> None:
        client_key = self._client_key()
        limiter = self.server.limiter_for(client_key)
        decision = limiter.check()

        if decision.allowed:
            body = json.dumps({"status": "ok", "client": client_key}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = json.dumps(
                {
                    "status": "rate_limited",
                    "client": client_key,
                    "retry_after": round(decision.retry_after, 3),
                }
            ).encode()
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", str(max(1, round(decision.retry_after))))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming convention)
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Silence default stderr access logging; callers can subclass or
        # monkeypatch this if they want request logs.
        pass


def serve_forever_in_thread(server: RateLimitedHTTPServer) -> threading.Thread:
    """Start ``server`` on a background daemon thread and return it."""
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread
