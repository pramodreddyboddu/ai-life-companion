"""Billing endpoints for Stripe checkout and portal."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_api_key
from app.db.models import ApiKey, PlanEnum, User
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])


def _get_billing_service() -> BillingService:
    return BillingService()


def _ensure_user(session: Session, api_key: ApiKey) -> User:
    user = session.get(User, api_key.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.post("/checkout")
def create_checkout_session(
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    billing: BillingService = Depends(_get_billing_service),
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
) -> dict:
    user = _ensure_user(session, api_key)

    base_url = "http://localhost:8000"
    success = success_url or f"{base_url}/billing/success"
    cancel = cancel_url or f"{base_url}/billing/cancel"

    checkout_url = billing.create_checkout_session(user, success_url=success, cancel_url=cancel)
    session.add(user)
    session.commit()
    return {"url": checkout_url}


@router.post("/portal")
def create_portal_session(
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    billing: BillingService = Depends(_get_billing_service),
    return_url: Optional[str] = None,
) -> dict:
    user = _ensure_user(session, api_key)
    base_url = "http://localhost:8000"
    url = billing.create_customer_portal(user, return_url=return_url or f"{base_url}/settings")
    return {"url": url}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: Session = Depends(get_db_session),
    billing: BillingService = Depends(_get_billing_service),
):
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe signature header.")

    try:
        billing.handle_webhook(payload, signature, session)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Stripe webhook error: %s", exc)
        raise HTTPException(status_code=400, detail="Webhook error") from exc

    return JSONResponse(status_code=200, content={"status": "success"})
