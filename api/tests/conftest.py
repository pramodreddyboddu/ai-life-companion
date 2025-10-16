from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import engine as app_engine
from app.settings import settings


def _alembic_config() -> Config:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config = Config(os.path.join(base_dir, "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database.url)
    config.set_main_option("script_location", os.path.join(base_dir, "alembic"))
    return config


@pytest.fixture(scope="session", autouse=True)
def apply_migrations() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")
    yield


@pytest.fixture(scope="session")
def engine():
    yield app_engine


@pytest.fixture()
def db_session(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    SessionFactory = sessionmaker(bind=connection, autoflush=False, autocommit=False, expire_on_commit=False)
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
