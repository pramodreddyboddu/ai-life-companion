"""FastAPI dependencies for shared concerns."""

from __future__ import annotations

import hmac
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApiKey, ApiKeyStatusEnum
from app.db.session import get_session
from app.security.api_keys import get_key_prefix, hash_api_key


def get_db_session() -> Iterator[Session]:
    """Provide a database session dependency."""

    yield from get_session()


def require_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    session: Session = Depends(get_db_session),
) -> ApiKey:
    """Validate the provided API key and return the corresponding record."""

    try:
        prefix = get_key_prefix(x_api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.") from exc

    query = (
        select(ApiKey)
        .where(ApiKey.prefix == prefix)
        .where(ApiKey.status == ApiKeyStatusEnum.ACTIVE)
        .limit(1)
    )
    api_key_record = session.execute(query).scalar_one_or_none()

    if api_key_record and hmac.compare_digest(api_key_record.key_hash, hash_api_key(x_api_key)):
        return api_key_record

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
