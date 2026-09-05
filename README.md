# rate-limiter-toolkit

Dependency-free Python implementations of the standard rate-limiting
algorithms, a threaded HTTP middleware demo built on the stdlib
`http.server`, and a load-test simulator that compares algorithms
head-to-head on throughput, rejection rate, and latency.

## What's in here

Five classic rate-limiting algorithms, all behind a common `RateLimiter`
interface (`allow()` / `check()`), all thread-safe, all pure Python 3.10+
stdlib:

- **Token bucket** (`TokenBucket`) — tokens refill continuously up to a
  capacity; requests consume tokens. Allows short bursts up to capacity
  while enforcing a long-run average rate.
- **Leaky bucket** (`LeakyBucket`) — a fill level that leaks (drains) at a
  constant rate; requests add to the level and are rejected on overflow.
  Smooths bursts into steady output rather than letting them through.
- **Fixed window counter** (`FixedWindowCounter`) — a counter per
  clock-aligned window (e.g. per-second). Cheap, but allows up to 2x the
  limit across a window boundary (a burst at the end of one window plus a
  burst at the start of the next).
- **Sliding window log** (`SlidingWindowLog`) — keeps a timestamp per
  admitted request and evicts ones older than the trailing window. Exact,
  no boundary-burst problem, but O(limit) memory and per-check work.
- **Sliding window counter** (`SlidingWindowCounter`) — approximates the
  sliding log in O(1) memory by blending two fixed-window counters,
  weighted by how far the clock is into the current window.

On top of the algorithms:

- **`ratelimiter.middleware`** — a `RateLimitedHTTPServer` (a
  `ThreadingHTTPServer` subclass) that rate-limits each client independently
  by an `X-Client-Id` header (falling back to the connecting IP), returning
  HTTP 429 with a `Retry-After` header once a client is over its limit.
- **`ratelimiter.simulator`** — fires concurrent requests at a limiter with
  a thread pool and reports allowed/rejected counts, rejection rate,
  requests/sec, and p50/p99 latency of the admission check itself.
- **`ratelimiter.cli`** (installed as `ratelimit-sim`) — a CLI wrapping both
  of the above: `compare` runs the simulator across all five algorithms,
  `serve` starts the demo HTTP server with a chosen algorithm.

## Tech stack

Python 3.10+, standard library only (`threading`, `http.server`,
`concurrent.futures`, `dataclasses`, `argparse`, `csv`). Test suite uses
`pytest`. No third-party runtime dependencies.

## How to run

```bash
git clone https://github.com/arnavchawla26/rate-limiter-toolkit.git
cd rate-limiter-toolkit
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

### Compare all five algorithms

```bash
ratelimit-sim compare --requests 2000 --concurrency 50 --limit 100 --window 1.0
```

Real output from running the command above:

```
Simulating 2000 requests at concurrency=50 against a limit of 100.0 per 1.0s window...

name             allowed  rejected  rej_rate  req/s   p50_ms  p99_ms
---------------  -------  --------  --------  ------  ------  ------
token_bucket     103      1897      94.85%    2630.5  0.001   0.006
leaky_bucket     103      1897      94.85%    2771.2  0.001   0.005
fixed_window     100      1900      95.00%    2326.7  0.001   0.006
sliding_log      100      1900      95.00%    2589.8  0.001   0.006
sliding_counter  100      1900      95.00%    2361.4  0.001   0.007
```

The ~95% rejection rate is expected, not a bug: firing 2000 requests as
fast as a thread pool can manage is a massive burst against a "100 per
second" budget delivered in a fraction of a second — see
`examples/sustained_vs_burst.py` below for the same limiter under paced
traffic that actually matches its rate.

### Run the demo HTTP server

```bash
ratelimit-sim serve --algorithm token_bucket --port 8000 --limit 3 --window 1
```

Real transcript from running the command above with `--limit 3` and then
issuing four requests with `curl`:

```
$ curl -i http://127.0.0.1:8321/
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 39

{"status": "ok", "client": "127.0.0.1"}

$ curl -i http://127.0.0.1:8321/   # request 2, still within the bucket
HTTP/1.0 200 OK
...
{"status": "ok", "client": "127.0.0.1"}

$ curl -i http://127.0.0.1:8321/   # request 3, exhausts the 3-token bucket
HTTP/1.0 200 OK
...
{"status": "ok", "client": "127.0.0.1"}

$ curl -i http://127.0.0.1:8321/   # request 4, rejected
HTTP/1.0 429 Too Many Requests
Content-Type: application/json
Retry-After: 1
Content-Length: 71

{"status": "rate_limited", "client": "127.0.0.1", "retry_after": 0.315}
```

### Examples

```bash
python examples/compare_algorithms.py     # same as `ratelimit-sim compare`, as library calls
python examples/sustained_vs_burst.py      # burst vs. paced traffic against the same limiter
```

Real output from `sustained_vs_burst.py`:

```
Burst (200 requests fired instantly):   20/200 allowed (10.0%)
Paced (40 requests at the limiter's own rate): 40/40 allowed (100.0%)
```

## Design notes

- Every limiter exposes `check(cost=1.0, now=None)` returning a `Decision`
  (`allowed`, `retry_after`) and `allow(...)` as a boolean convenience
  wrapper. `now` is injectable for deterministic tests; it defaults to
  `time.monotonic()`.
- Every limiter tracks running `stats` (`allowed`, `rejected`,
  `rejection_rate`) for introspection without needing the simulator.
- All five implementations use a single `threading.Lock` per instance and
  are safe to call from multiple threads; `test_token_bucket.py` includes a
  concurrency test asserting exactly `capacity` requests are admitted out
  of 500 simultaneous callers.
- The HTTP middleware and the simulator are independent consumers of the
  same `RateLimiter` interface — the middleware demonstrates per-client
  isolation over a network boundary, the simulator demonstrates raw
  algorithm behavior without any network overhead in the numbers.

## Current status

**v1, functional and tested.** All five algorithms, the HTTP middleware,
the load-test simulator, and the CLI are implemented and covered by tests
(pytest, stdlib `unittest`-free). Every output block above — the `compare`
table, the `curl` transcript against the live demo server, and both example
scripts — is copied verbatim from actually running the commands, not
hand-written.

Possible future extensions (not started): a distributed/Redis-backed
variant of one of the algorithms for multi-process deployments; a
`--sustained` mode on the `compare` subcommand that paces the simulator's
requests instead of firing them all at once; per-algorithm capacity/rate
auto-tuning suggestions based on observed traffic.

## License

MIT — see [LICENSE](LICENSE).
