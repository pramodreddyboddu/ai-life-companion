from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_calendar_service
from app.api.deps import get_db_session
from app.db.models import ApiKey, ApiKeyStatusEnum, PlanEnum, User
from app.main import app
from app.security.api_keys import get_key_prefix, hash_api_key
from app.settings import settings


@pytest.fixture(autouse=True)
def stripe_settings(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_123")
    monkeypatch.setattr(settings, "stripe_price_pro", "price_test_pro")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    yield


@pytest.fixture()
def api_client(db_session):
    def override_db_session():
        return db_session

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_webhook_updates_plan(monkeypatch, api_client, db_session):
    user = User(id=uuid.uuid4(), email="billing@example.com", plan=PlanEnum.FREE, stripe_customer_id="cus_test")
    db_session.add(user)
    db_session.commit()

    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "customer": "cus_test",
                "id": "sub_test",
                "status": "active",
            }
        },
    }

    monkeypatch.setattr(
        "stripe.Webhook.construct_event",
        lambda payload, sig, secret: event,
    )

    response = api_client.post(
        "/billing/webhook",
        headers={"Stripe-Signature": "test"},
        data=b"{}",
    )
    assert response.status_code == 200

    db_session.refresh(user)
    assert user.plan == PlanEnum.PRO
    assert user.stripe_subscription_id == "sub_test"


def test_agenda_requires_pro_plan(api_client, db_session):
    user = User(id=uuid.uuid4(), email="free@example.com", plan=PlanEnum.FREE)
    db_session.add(user)
    db_session.flush()

    api_key_value = "sk-free-plan"
    api_key = ApiKey(
        user_id=user.id,
        prefix=get_key_prefix(api_key_value),
        key_hash=hash_api_key(api_key_value),
        status=ApiKeyStatusEnum.ACTIVE,
    )
    db_session.add(api_key)
    db_session.commit()

    response = api_client.get(
        "/agenda",
        headers={"X-API-Key": api_key_value},
    )
    assert response.status_code == 402


def test_stt_requires_pro_plan(api_client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-whisper")
    user = User(id=uuid.uuid4(), email="voice@example.com", plan=PlanEnum.FREE)
    db_session.add(user)
    db_session.flush()
    api_key_value = "sk-voice-plan"
    api_key = ApiKey(
        user_id=user.id,
        prefix=get_key_prefix(api_key_value),
        key_hash=hash_api_key(api_key_value),
        status=ApiKeyStatusEnum.ACTIVE,
    )
    db_session.add(api_key)
    db_session.commit()

    files = {"file": ("speech.m4a", b"dummy", "audio/m4a")}
    response = api_client.post(
        "/stt",
        headers={"X-API-Key": api_key_value},
        files=files,
    )
    assert response.status_code == 402
