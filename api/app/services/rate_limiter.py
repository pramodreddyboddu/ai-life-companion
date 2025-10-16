"""Simple per-user rate limiter backed by Redis."""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol
import uuid


class SupportsRedis(Protocol):
    """Duck-typed subset of Redis client methods used by the limiter."""

    def incr(self, name: str) -> int: ...

    def expire(self, name: str, time: int) -> None: ...


class RateLimitExceeded(Exception):
    """Raised when a caller exceeds the configured rate limit."""


class RateLimiter:
    """Track request counts per user within a fixed window."""

    def __init__(self, redis_client: SupportsRedis, *, limit: int, window_seconds: int) -> None:
        self._redis = redis_client
        self._limit = limit
        self._window_seconds = window_seconds

    @property
    def window(self) -> timedelta:
        return timedelta(seconds=self._window_seconds)

    def check(self, user_id: uuid.UUID) -> None:
        """Increment the user's counter and raise if the limit is exceeded."""

        key = f"rate-limit:chat:{user_id}"
        current_count = self._redis.incr(key)

        if current_count == 1:
            self._redis.expire(key, self._window_seconds)

        if current_count > self._limit:
            raise RateLimitExceeded(f"Rate limit exceeded for user {user_id}")
