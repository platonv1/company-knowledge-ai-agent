"""Rate limiting.

An unauthenticated chat endpoint in front of a paid model is an open LLM proxy,
so this is a Phase 1 requirement rather than a hardening task for later.

The clock is injected so the tests are deterministic and never sleep.
"""

from app.core.rate_limit import TokenBucketLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_requests_within_the_limit_are_allowed():
    limiter = TokenBucketLimiter(per_minute=3, clock=FakeClock())

    assert [limiter.allow("1.2.3.4") for _ in range(3)] == [True, True, True]


def test_the_request_over_the_limit_is_blocked():
    limiter = TokenBucketLimiter(per_minute=2, clock=FakeClock())

    limiter.allow("1.2.3.4")
    limiter.allow("1.2.3.4")

    assert limiter.allow("1.2.3.4") is False


def test_clients_are_limited_independently():
    limiter = TokenBucketLimiter(per_minute=1, clock=FakeClock())

    assert limiter.allow("1.1.1.1") is True
    assert limiter.allow("2.2.2.2") is True
    assert limiter.allow("1.1.1.1") is False


def test_allowance_refills_over_time():
    clock = FakeClock()
    limiter = TokenBucketLimiter(per_minute=60, clock=clock)

    assert limiter.allow("1.2.3.4") is True
    for _ in range(59):
        limiter.allow("1.2.3.4")
    assert limiter.allow("1.2.3.4") is False

    clock.advance(2.0)  # 60/min refills one token per second

    assert limiter.allow("1.2.3.4") is True


def test_allowance_never_exceeds_the_burst_limit():
    clock = FakeClock()
    limiter = TokenBucketLimiter(per_minute=5, clock=clock)

    clock.advance(3600)  # idle for an hour

    assert [limiter.allow("1.2.3.4") for _ in range(6)] == [True] * 5 + [False]


def test_retry_after_reports_when_the_next_token_arrives():
    clock = FakeClock()
    limiter = TokenBucketLimiter(per_minute=60, clock=clock)

    for _ in range(60):
        limiter.allow("1.2.3.4")

    assert 0 < limiter.retry_after("1.2.3.4") <= 1.0


def test_idle_clients_are_evicted_so_memory_does_not_grow_without_bound():
    clock = FakeClock()
    limiter = TokenBucketLimiter(per_minute=5, clock=clock, idle_eviction_seconds=60)

    limiter.allow("1.1.1.1")
    assert limiter.tracked_clients == 1

    clock.advance(120)
    limiter.allow("2.2.2.2")

    assert limiter.tracked_clients == 1
