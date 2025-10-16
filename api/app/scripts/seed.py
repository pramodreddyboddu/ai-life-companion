"""Seed canonical personas and a demo user with API key."""

from __future__ import annotations

import os

from loguru import logger
from sqlalchemy import select

from app.db.models import ApiKey, ApiKeyStatusEnum, PlanEnum, User, Persona
from app.db.session import SessionLocal
from app.security.api_keys import get_key_prefix, hash_api_key
from app.services.chat_orchestrator import DEFAULT_PERSONAS

DEFAULT_USER_EMAIL = os.environ.get("SEED_USER_EMAIL", "demo@example.com")
DEFAULT_API_KEY = os.environ.get("SEED_API_KEY", "sk-demo-accountability")


def _ensure_personas(session) -> None:
    for key, config in DEFAULT_PERSONAS.items():
        persona = session.execute(select(Persona).where(Persona.key == key)).scalar_one_or_none()
        if persona:
            updated = False
            if persona.name != config["name"]:
                persona.name = config["name"]
                updated = True
            if persona.system_prompt != config["system_prompt"]:
                persona.system_prompt = config["system_prompt"]
                updated = True
            if updated:
                session.add(persona)
            logger.info("Updated persona '{}'.", key)
        else:
            logger.info("Creating persona '{}'.", key)
            session.add(
                Persona(
                    key=key,
                    name=config["name"],
                    system_prompt=config["system_prompt"],
                )
            )


def _ensure_demo_user(session) -> None:
    user = session.execute(select(User).where(User.email == DEFAULT_USER_EMAIL)).scalar_one_or_none()
    if user is None:
        user = User(email=DEFAULT_USER_EMAIL, plan=PlanEnum.PRO.value)
        session.add(user)
        session.flush()
        logger.info("Created demo user '{}'.", user.email)

    prefix = get_key_prefix(DEFAULT_API_KEY)
    api_key = session.execute(select(ApiKey).where(ApiKey.prefix == prefix)).scalar_one_or_none()
    if api_key is None:
        api_key = ApiKey(
            user_id=user.id,
            prefix=prefix,
            key_hash=hash_api_key(DEFAULT_API_KEY),
            status=ApiKeyStatusEnum.ACTIVE,
        )
        session.add(api_key)
        logger.info("Provisioned demo API key with prefix '{}'.", api_key.prefix)

    print(f"DEMO_API_KEY={DEFAULT_API_KEY}")


def main() -> None:
    session = SessionLocal()
    try:
        _ensure_personas(session)
        _ensure_demo_user(session)
        session.commit()
        logger.info("Seed complete.")
    except Exception as exc:  # pylint: disable=broad-except
        session.rollback()
        logger.error("Seed failed: %s", exc)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
