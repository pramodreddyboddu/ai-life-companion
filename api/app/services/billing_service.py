"""Stripe billing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import uuid

import stripe
from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import User, PlanEnum
from app.settings import settings


@dataclass
class BillingConfig:
    price_id_pro: str
    webhook_secret: str


def _ensure_stripe_config() -> BillingConfig:
    if not settings.stripe_secret_key or not settings.stripe_price_pro or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Billing is not configured.")
    stripe.api_key = settings.stripe_secret_key
    return BillingConfig(price_id_pro=settings.stripe_price_pro, webhook_secret=settings.stripe_webhook_secret)


class BillingService:
    """Encapsulate Stripe subscription flows."""

    def __init__(self) -> None:
        self._config = _ensure_stripe_config()

    def create_checkout_session(self, user: User, success_url: str, cancel_url: str) -> str:
        customer_id = user.stripe_customer_id or self._create_customer(user)

        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": self._config.price_id_pro, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return session.url

    def create_customer_portal(self, user: User, return_url: str) -> str:
        if not user.stripe_customer_id:
            raise HTTPException(status_code=400, detail="No billing information for this user.")

        portal = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=return_url,
        )
        return portal.url

    def handle_webhook(self, payload: bytes, signature: str, session: Session) -> None:
        event = stripe.Webhook.construct_event(payload, signature, self._config.webhook_secret)

        event_type = event["type"]
        logger.info("Received Stripe event: {}", event_type)

        if event_type == "checkout.session.completed":
            self._process_checkout_completed(event["data"]["object"], session)
        elif event_type in {"customer.subscription.updated", "customer.subscription.created"}:
            self._process_subscription_updated(event["data"]["object"], session)
        elif event_type == "customer.subscription.deleted":
            self._process_subscription_deleted(event["data"]["object"], session)
        else:
            logger.debug("Unhandled Stripe event type {}", event_type)

    def _create_customer(self, user: User) -> str:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={
                "user_id": str(user.id),
            },
        )
        user.stripe_customer_id = customer.id
        return customer.id

    def _process_checkout_completed(self, payload: dict, session: Session) -> None:
        customer_id = payload.get("customer")
        subscription_id = payload.get("subscription")
        lookup_key = payload.get("client_reference_id") or payload.get("metadata", {}).get("user_id")

        logger.info("Checkout completed for customer {}", customer_id)
        user = self._find_user(session, customer_id=customer_id, fallback_user_id=lookup_key)
        if not user:
            logger.warning("Unable to locate user for checkout session (customer {})", customer_id)
            return

        user.stripe_customer_id = customer_id
        if subscription_id:
            user.stripe_subscription_id = subscription_id
            user.plan = PlanEnum.PRO
        session.add(user)
        session.commit()

    def _process_subscription_updated(self, payload: dict, session: Session) -> None:
        customer_id = payload.get("customer")
        subscription_id = payload.get("id")
        status_value = payload.get("status")

        logger.info("Subscription updated {} status {}", subscription_id, status_value)

        user = self._find_user(session, customer_id=customer_id, subscription_id=subscription_id)
        if not user:
            logger.warning("Unable to locate user for subscription {}", subscription_id)
            return

        user.stripe_subscription_id = subscription_id
        if status_value in {"active", "trialing", "past_due"}:
            user.plan = PlanEnum.PRO
        else:
            user.plan = PlanEnum.FREE
        session.add(user)
        session.commit()

    def _process_subscription_deleted(self, payload: dict, session: Session) -> None:
        customer_id = payload.get("customer")
        subscription_id = payload.get("id")

        logger.info("Subscription deleted {}", subscription_id)

        user = self._find_user(session, customer_id=customer_id, subscription_id=subscription_id)
        if not user:
            return

        user.plan = PlanEnum.FREE
        user.stripe_subscription_id = None
        session.add(user)
        session.commit()

    def _find_user(
        self,
        session: Session,
        *,
        customer_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        fallback_user_id: Optional[str] = None,
    ) -> Optional[User]:
        query = session.query(User)
        if customer_id:
            user = query.filter(User.stripe_customer_id == customer_id).first()
            if user:
                return user
        if subscription_id:
            user = query.filter(User.stripe_subscription_id == subscription_id).first()
            if user:
                return user
        if fallback_user_id:
            try:
                user_uuid = fallback_user_id if isinstance(fallback_user_id, uuid.UUID) else uuid.UUID(str(fallback_user_id))
                return session.get(User, user_uuid)
            except Exception:  # pylint: disable=broad-except
                return None
        return None
