from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from studio_worker import tenants_db
from studio_worker.billing_config import stripe_webhook_secret
from studio_worker.stripe_billing import (
    billing_catalog_public_flags,
    create_checkout_session_url,
    create_portal_session_url,
    handle_stripe_event,
)
from studio_worker.tenant_context import RequestTenant, get_request_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/studio/billing", tags=["billing"])


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
) -> dict[str, bool]:
    """
    Stripe sends raw body + Stripe-Signature. Configure endpoint in Dashboard → Developers → Webhooks.
    """
    secret = stripe_webhook_secret()
    if not secret:
        logger.error("stripe_webhook_reject missing STRIPE_WEBHOOK_SECRET")
        raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET is not set")

    sig = stripe_signature or request.headers.get("Stripe-Signature")
    if not sig:
        logger.warning("stripe_webhook_reject missing Stripe-Signature header")
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    body = await request.body()

    import stripe

    try:
        event = stripe.Webhook.construct_event(body, sig, secret)
    except ValueError as e:
        logger.warning("stripe_webhook_reject invalid_payload: %s", e)
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}") from e
    except stripe.error.SignatureVerificationError as e:
        logger.warning("stripe_webhook_reject invalid_signature: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature") from e

    eid = getattr(event, "id", None)
    etype = getattr(event, "type", None)

    try:
        handle_stripe_event(event)
    except Exception:
        logger.exception(
            "stripe_webhook_handler_failed event_id=%s type=%s",
            eid,
            etype,
        )
        raise HTTPException(status_code=500, detail="Webhook handler failed") from None

    logger.debug("stripe_webhook_ok event_id=%s type=%s", eid, etype)
    return {"received": True}


class CheckoutSessionRequest(BaseModel):
    tier: Literal["indie", "team"] = Field(description="Subscription tier to purchase")


class CheckoutSessionResponse(BaseModel):
    url: str


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
def post_checkout_session(
    body: CheckoutSessionRequest,
    tenant: RequestTenant = Depends(get_request_tenant),
) -> CheckoutSessionResponse:
    if not tenant.limits_enforced:
        raise HTTPException(
            status_code=400,
            detail="Checkout requires SaaS mode (STUDIO_API_AUTH_REQUIRED=1) and a tenant API key.",
        )
    try:
        url = create_checkout_session_url(tenant_id=tenant.tenant_id, tier=body.tier)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return CheckoutSessionResponse(url=url)


class PortalSessionResponse(BaseModel):
    url: str


@router.post("/portal-session", response_model=PortalSessionResponse)
def post_portal_session(
    tenant: RequestTenant = Depends(get_request_tenant),
) -> PortalSessionResponse:
    if not tenant.limits_enforced:
        raise HTTPException(
            status_code=400,
            detail="Portal requires SaaS mode and a tenant API key.",
        )
    try:
        url = create_portal_session_url(tenant_id=tenant.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return PortalSessionResponse(url=url)


@router.get("/status")
def get_billing_status(
    tenant: RequestTenant = Depends(get_request_tenant),
) -> dict[str, Any]:
    pub = billing_catalog_public_flags()
    out: dict[str, Any] = {
        **pub,
        "tier_id": tenant.tier_id,
        "stripe_customer_linked": False,
        "stripe_subscription_id": None,
    }
    if tenant.limits_enforced:
        row = tenants_db.get_tenant(tenant.tenant_id)
        if row:
            out["stripe_customer_linked"] = bool(row.get("stripe_customer_id"))
            out["stripe_subscription_id"] = row.get("stripe_subscription_id")
    return out
