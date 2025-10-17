"""Simple per-user/API-key rate limiter backed by Redis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import uuid


class SupportsRedis(Protocol):
    """Subset of Redis methods used by the limiter."""

    def incr(self, name: str) -> int: ...

    def expire(self, name: str, time: int) -> None: ...


class RateLimitExceeded(Exception):
    """Raised when a caller exceeds the configured rate limit."""

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class RateLimitConfig:
    burst_limit: int
    burst_window_seconds: int
    sustained_limit: int
    sustained_window_seconds: int


class RateLimiter:
    """Track request counts within burst and sustained windows."""

    def __init__(self, redis_client: SupportsRedis, config: RateLimitConfig) -> None:
        self._redis = redis_client
        self._config = config

    def _check_window(self, key: str, limit: int, window_seconds: int) -> int:
        current = self._redis.incr(key)
        if current == 1:
            self._redis.expire(key, window_seconds)
        return current

    def check(self, identifier: uuid.UUID | str) -> None:
        """Increment counters for the identifier and raise when limits are exceeded."""

        identifier_str = str(identifier)
        burst_key = f"rate-limit:chat:burst:{identifier_str}"
        sustained_key = f"rate-limit:chat:sustained:{identifier_str}"

        burst_count = self._check_window(
            burst_key, self._config.burst_limit, self._config.burst_window_seconds
        )
        if burst_count > self._config.burst_limit:
            raise RateLimitExceeded(
                "Burst rate limit exceeded.",
                retry_after_seconds=self._config.burst_window_seconds,
            )

        sustained_count = self._check_window(
            sustained_key, self._config.sustained_limit, self._config.sustained_window_seconds
        )
        if sustained_count > self._config.sustained_limit:
            raise RateLimitExceeded(
                "Hourly rate limit exceeded.",
                retry_after_seconds=self._config.sustained_window_seconds,
            )
