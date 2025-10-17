"""Feature flag service for runtime toggles."""

from __future__ import annotations

import os
import time
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FeatureFlag
from app.db.session import SessionLocal

BOOL_TRUE = {"1", "true", "yes", "on"}
ENV_PREFIX = "FEATURE_FLAG_"


class FeatureFlagService:
    """Read and write feature flags with optional env overrides."""

    def __init__(self, cache_ttl_seconds: int = 30) -> None:
        self._cache: Dict[str, Tuple[bool, float]] = {}
        self._ttl = cache_ttl_seconds

    # ------------------------------------------------------------------
    def is_enabled(self, key: str, *, session: Optional[Session] = None) -> bool:
        override = self._env_override(key)
        if override is not None:
            return override

        now = time.time()
        cached = self._cache.get(key)
        if cached and now - cached[1] < self._ttl:
            return cached[0]

        if session is None:
            with SessionLocal() as db:
                value = self._load_flag(db, key)
        else:
            value = self._load_flag(session, key)

        self._cache[key] = (value, now)
        return value

    def set_flag(self, session: Session, key: str, enabled: bool, description: Optional[str] = None) -> FeatureFlag:
        record = session.execute(select(FeatureFlag).where(FeatureFlag.key == key)).scalar_one_or_none()
        if record is None:
            record = FeatureFlag(key=key, enabled=enabled, description=description)
            session.add(record)
        else:
            record.enabled = enabled
            if description is not None:
                record.description = description
        session.commit()
        self._cache[key] = (enabled, time.time())
        return record

    def list_flags(self, session: Session) -> List[FeatureFlag]:
        return session.execute(select(FeatureFlag)).scalars().all()

    def describe_flags(self, session: Session) -> List[Dict[str, Optional[str]]]:
        flags = self.list_flags(session)
        results: List[Dict[str, Optional[str]]] = []
        seen_keys = set()
        for flag in flags:
            override = self._env_override(flag.key)
            effective = override if override is not None else bool(flag.enabled)
            results.append(
                {
                    "key": flag.key,
                    "enabled": bool(flag.enabled),
                    "effective": effective,
                    "override": override,
                    "description": flag.description,
                    "updated_at": flag.updated_at.isoformat() if flag.updated_at else None,
                }
            )
            seen_keys.add(flag.key)

        # include env-only flags
        for env_key, value in os.environ.items():
            if not env_key.startswith(ENV_PREFIX):
                continue
            key = env_key[len(ENV_PREFIX) :].lower()
            if key in seen_keys:
                continue
            override = self._env_override(key)
            results.append(
                {
                    "key": key,
                    "enabled": False,
                    "effective": override,
                    "override": override,
                    "description": "Env override",
                    "updated_at": None,
                }
            )
        return results

    def invalidate(self, key: Optional[str] = None) -> None:
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    # ------------------------------------------------------------------
    def _load_flag(self, session: Session, key: str) -> bool:
        record = session.execute(select(FeatureFlag).where(FeatureFlag.key == key)).scalar_one_or_none()
        return bool(record.enabled) if record else False

    def _env_override(self, key: str) -> Optional[bool]:
        env_key = f"{ENV_PREFIX}{key.upper()}"
        if env_key in os.environ:
            return os.environ[env_key].lower() in BOOL_TRUE
        return None
