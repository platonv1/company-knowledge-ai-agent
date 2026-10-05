"""In-process token bucket rate limiting.

Correct for a single instance, which is what Phase 1 deploys. Behind a load
balancer each instance would keep its own counters, so the effective limit
multiplies by the instance count -- at that point this needs to move to Redis.
The limitation is deliberate and documented rather than designed around now.
"""

import time
from collections.abc import Callable

from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_IDLE_EVICTION_SECONDS = 600


class TokenBucketLimiter:
    """Allows `per_minute` requests per client, refilling continuously.

    A bucket rather than a fixed window: a fixed window lets a client spend its
    whole allowance twice across a window boundary.
    """

    def __init__(
        self,
        per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        idle_eviction_seconds: float = DEFAULT_IDLE_EVICTION_SECONDS,
    ):
        if per_minute < 1:
            raise ValueError("per_minute must be at least 1.")
        self._capacity = float(per_minute)
        self._refill_per_second = per_minute / 60.0
        self._clock = clock
        self._idle_eviction_seconds = idle_eviction_seconds
        # client -> (tokens remaining, last update)
        self._buckets: dict[str, tuple[float, float]] = {}

    @property
    def tracked_clients(self) -> int:
        return len(self._buckets)

    def _evict_idle(self, now: float) -> None:
        cutoff = now - self._idle_eviction_seconds
        stale = [key for key, (_, seen) in self._buckets.items() if seen < cutoff]
        for key in stale:
            del self._buckets[key]

    def _tokens(self, key: str, now: float) -> float:
        tokens, last_seen = self._buckets.get(key, (self._capacity, now))
        refilled = tokens + (now - last_seen) * self._refill_per_second
        return min(refilled, self._capacity)

    def allow(self, key: str) -> bool:
        now = self._clock()
        self._evict_idle(now)

        tokens = self._tokens(key, now)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False

        self._buckets[key] = (tokens - 1.0, now)
        return True

    def retry_after(self, key: str) -> float:
        """Seconds until one more request is allowed."""
        now = self._clock()
        tokens = self._tokens(key, now)
        if tokens >= 1.0:
            return 0.0
        return (1.0 - tokens) / self._refill_per_second
