"""Service factories and singletons used across API routes."""

from __future__ import annotations

from functools import lru_cache

from openai import OpenAI
from redis import Redis

from app.services.calendar_service import CalendarService
from app.services.chat_orchestrator import ChatOrchestrator
from app.services.embedding_service import EmbeddingService
from app.services.feature_flags import FeatureFlagService
from app.services.memory_service import MemoryService
from app.services.metrics_service import MetricsService
from app.services.rate_limiter import RateLimitConfig, RateLimiter
from app.services.safety import SafetyService
from app.settings import settings


@lru_cache(maxsize=1)
def _embedding_service() -> EmbeddingService:
    return EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    return _embedding_service()


@lru_cache(maxsize=1)
def _memory_service() -> MemoryService:
    return MemoryService(_embedding_service())


@lru_cache(maxsize=1)
def _safety_service() -> SafetyService:
    return SafetyService()


def get_memory_service() -> MemoryService:
    return _memory_service()


def get_safety_service() -> SafetyService:
    return _safety_service()


@lru_cache(maxsize=1)
def _calendar_service() -> CalendarService:
    return CalendarService()


def get_calendar_service() -> CalendarService:
    return _calendar_service()


@lru_cache(maxsize=1)
def _openai_client() -> OpenAI:
    if settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key)
    return OpenAI()


@lru_cache(maxsize=1)
def _rate_limiter() -> RateLimiter:
    redis_client = Redis.from_url(settings.redis.url, decode_responses=True)
    config = RateLimitConfig(
        burst_limit=10,
        burst_window_seconds=60,
        sustained_limit=60,
        sustained_window_seconds=3600,
    )
    return RateLimiter(redis_client, config)


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter()



@lru_cache(maxsize=1)
def _feature_flag_service() -> FeatureFlagService:
    return FeatureFlagService()


def get_feature_flag_service() -> FeatureFlagService:
    return _feature_flag_service()

@lru_cache(maxsize=1)
def _metrics_service() -> MetricsService:
    return MetricsService()


def get_metrics_service() -> MetricsService:
    return _metrics_service()


@lru_cache(maxsize=1)
def _chat_orchestrator() -> ChatOrchestrator:
    return ChatOrchestrator(
        openai_client=_openai_client().chat.completions,
        embedding_service=_embedding_service(),
        memory_service=_memory_service(),
        rate_limiter=_rate_limiter(),
        metrics_service=_metrics_service(),
        calendar_service=_calendar_service(),
        safety_service=_safety_service(),
    )


def get_chat_orchestrator() -> ChatOrchestrator:
    return _chat_orchestrator()
