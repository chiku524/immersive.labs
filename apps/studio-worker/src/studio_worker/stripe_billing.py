from __future__ import annotations

import logging
from typing import Any

from studio_worker import tenants_db
from studio_worker.billing_config import (
    billing_cancel_url,
    billing_portal_return_url,
    billing_success_url,
    price_id_for_tier,
    resolve_tier_for_price,
    stripe_api_version,
    stripe_secret_key,
    trial_end_notify_webhook_url,
)

logger = logging.getLogger(__name__)


def configure_stripe() -> None:
    import stripe

    key = stripe_secret_key()
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY is not set")
    stripe.api_key = key
    ver = stripe_api_version()
    if ver:
        stripe.api_version = ver


def _as_dict_meta(obj: Any) -> dict[str, str]:
    try:
        if isinstance(obj, dict):
            m = obj.get("metadata") or {}
        else:
            m = getattr(obj, "metadata", None) or {}
        return {str(k): str(v) for k, v in dict(m).items()}
    except Exception:
        return {}


def tier_from_subscription_object(sub: Any) -> str:
    if isinstance(sub, dict):
        items = (sub.get("items") or {}).get("data") or []
    else:
        items = list(getattr(getattr(sub, "items", None), "data", []) or [])
    if not items:
        return "free"
    first = items[0]
    price = first.get("price") if isinstance(first, dict) else getattr(first, "price", None)
    if price is None:
        return "free"
    tier = resolve_tier_for_price(price)
    return tier if tier else "free"


def _subscription_status(sub: Any) -> str:
    s = sub.get("status") if isinstance(sub, dict) else getattr(sub, "status", None)
    return str(s) if s is not None else ""


def apply_subscription_to_tenant(tenant_id: str, subscription_id: str) -> None:
    configure_stripe()
    import stripe

    sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
    tier = tier_from_subscription_object(sub)
    status = _subscription_status(sub)
    tenants_db.set_stripe_subscription_id(tenant_id, subscription_id)
    if status in ("active", "trialing", "past_due"):
        tenants_db.set_tenant_tier(tenant_id, tier)
    elif status in ("canceled", "unpaid", "incomplete_expired"):
        tenants_db.set_tenant_tier(tenant_id, "free")
    else:
        # incomplete (e.g. async payment pending) — no paid tier until active
        tenants_db.set_tenant_tier(tenant_id, "free")


def _checkout_session_tenant_id(session: Any) -> str | None:
    meta = _as_dict_meta(session)
    tenant_id = meta.get("tenant_id") or (
        session.get("client_reference_id")
        if isinstance(session, dict)
        else getattr(session, "client_reference_id", None)
    )
    return str(tenant_id) if tenant_id else None


def _checkout_session_tenant_and_ids(session: Any) -> tuple[str | None, str | None, str | None]:
    tenant_id = _checkout_session_tenant_id(session)
    cust = session.get("customer") if isinstance(session, dict) else getattr(session, "customer", None)
    sub = session.get("subscription") if isinstance(session, dict) else getattr(session, "subscription", None)
    if not tenant_id or not cust or not sub:
        return None, None, None
    return str(tenant_id), str(cust), str(sub)


def handle_checkout_session_completed(session: Any) -> None:
    mode = session.get("mode") if isinstance(session, dict) else getattr(session, "mode", None)
    if mode != "subscription":
        return
    tenant_id_s, cust_s, sub_s = _checkout_session_tenant_and_ids(session)
    if not tenant_id_s or not cust_s or not sub_s:
        logger.warning("checkout session missing tenant_id, customer, or subscription")
        return
    tenants_db.link_stripe_customer(tenant_id_s, cust_s)
    tenants_db.set_stripe_subscription_id(tenant_id_s, sub_s)
    apply_subscription_to_tenant(tenant_id_s, sub_s)


def handle_checkout_session_async_payment_succeeded(session: Any) -> None:
    """Delayed payment methods (e.g. bank debit): entitlements after funds settle."""
    handle_checkout_session_completed(session)


def handle_checkout_session_async_payment_failed(session: Any) -> None:
    mode = session.get("mode") if isinstance(session, dict) else getattr(session, "mode", None)
    if mode != "subscription":
        return
    tenant_id_s = _checkout_session_tenant_id(session)
    cust = session.get("customer") if isinstance(session, dict) else getattr(session, "customer", None)
    cust_s = str(cust) if cust else None
    if not tenant_id_s:
        logger.warning("checkout.session.async_payment_failed missing tenant_id on session")
        return
    if cust_s:
        try:
            tenants_db.link_stripe_customer(tenant_id_s, cust_s)
        except ValueError:
            logger.warning("Could not link Stripe customer on async_payment_failed")
    tenants_db.set_stripe_subscription_id(tenant_id_s, None)
    tenants_db.set_tenant_tier(tenant_id_s, "free")
    logger.warning("Async checkout payment failed for tenant %s", tenant_id_s[:8])


def handle_checkout_session_expired(session: Any) -> None:
    logger.debug("checkout.session.expired (no tenant changes)")


def handle_subscription_updated(sub: Any) -> None:
    cust = sub.get("customer") if isinstance(sub, dict) else getattr(sub, "customer", None)
    if not cust:
        return
    cust_s = str(cust)
    row = tenants_db.find_tenant_by_stripe_customer(cust_s)
    meta = _as_dict_meta(sub)
    if not row and meta.get("tenant_id"):
        try:
            tenants_db.link_stripe_customer(str(meta["tenant_id"]), cust_s)
            row = tenants_db.find_tenant_by_stripe_customer(cust_s)
        except ValueError:
            logger.warning("Could not link Stripe customer to tenant from subscription metadata")
            return
    if not row:
        logger.warning("subscription event: no tenant for customer %s…", cust_s[:10])
        return
    tid = str(row["id"])
    sub_id = sub.get("id") if isinstance(sub, dict) else sub.id
    status = sub.get("status") if isinstance(sub, dict) else sub.status
    tenants_db.set_stripe_subscription_id(tid, str(sub_id))
    if status in ("active", "trialing", "past_due"):
        tenants_db.set_tenant_tier(tid, tier_from_subscription_object(sub))
    elif status in ("canceled", "unpaid", "incomplete_expired"):
        tenants_db.set_tenant_tier(tid, "free")
    else:
        tenants_db.set_tenant_tier(tid, tier_from_subscription_object(sub))


def handle_subscription_deleted(sub: Any) -> None:
    cust = sub.get("customer") if isinstance(sub, dict) else getattr(sub, "customer", None)
    if not cust:
        return
    row = tenants_db.find_tenant_by_stripe_customer(str(cust))
    if not row:
        return
    tid = str(row["id"])
    tenants_db.set_stripe_subscription_id(tid, None)
    tenants_db.set_tenant_tier(tid, "free")


def _post_trial_will_end_notification(payload: dict[str, Any]) -> None:
    url = trial_end_notify_webhook_url()
    if not url:
        return
    try:
        import httpx

        r = httpx.post(url, json=payload, timeout=15.0)
        r.raise_for_status()
    except Exception:
        logger.warning("STUDIO_TRIAL_END_NOTIFY_WEBHOOK_URL request failed", exc_info=True)


def handle_subscription_trial_will_end(sub: Any) -> None:
    cust = sub.get("customer") if isinstance(sub, dict) else getattr(sub, "customer", None)
    sub_id = sub.get("id") if isinstance(sub, dict) else getattr(sub, "id", None)
    trial_end = sub.get("trial_end") if isinstance(sub, dict) else getattr(sub, "trial_end", None)
    tenant_id: str | None = None
    if cust:
        row = tenants_db.find_tenant_by_stripe_customer(str(cust))
        if row:
            tenant_id = str(row["id"])
    logger.info(
        "stripe_subscription_trial_will_end tenant=%s subscription=%s trial_end=%s",
        tenant_id or "-",
        sub_id,
        trial_end,
    )
    _post_trial_will_end_notification(
        {
            "event": "customer.subscription.trial_will_end",
            "tenant_id": tenant_id,
            "stripe_customer_id": str(cust) if cust else None,
            "stripe_subscription_id": str(sub_id) if sub_id else None,
            "trial_end": trial_end,
        }
    )


def handle_stripe_event(event: Any) -> None:
    et = event.get("type") if isinstance(event, dict) else event.type
    data_obj = (
        event.get("data", {}).get("object")
        if isinstance(event, dict)
        else event.data.object
    )
    if et == "checkout.session.completed":
        handle_checkout_session_completed(data_obj)
    elif et == "checkout.session.async_payment_succeeded":
        handle_checkout_session_async_payment_succeeded(data_obj)
    elif et == "checkout.session.async_payment_failed":
        handle_checkout_session_async_payment_failed(data_obj)
    elif et == "checkout.session.expired":
        handle_checkout_session_expired(data_obj)
    elif et in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.pending_update_applied",
        "customer.subscription.pending_update_expired",
    ):
        handle_subscription_updated(data_obj)
    elif et == "customer.subscription.deleted":
        handle_subscription_deleted(data_obj)
    elif et == "customer.subscription.trial_will_end":
        handle_subscription_trial_will_end(data_obj)
    else:
        logger.debug("Ignoring Stripe event type %s", et)


def create_checkout_session_url(*, tenant_id: str, tier: str) -> str:
    configure_stripe()
    import stripe

    tier_l = tier.strip().lower()
    if tier_l not in ("indie", "team"):
        raise ValueError("Checkout is only available for indie or team tiers.")
    price = price_id_for_tier(tier_l)
    if not price:
        raise ValueError(
            f"Set STUDIO_STRIPE_PRICE_{tier_l.upper()} (or STUDIO_STRIPE_PRICE_MAP) to your Stripe Price id."
        )
    ex = tenants_db.get_tenant(tenant_id)
    if not ex:
        raise ValueError("Unknown tenant")
    params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price, "quantity": 1}],
        "success_url": billing_success_url(),
        "cancel_url": billing_cancel_url(),
        "client_reference_id": tenant_id,
        "metadata": {"tenant_id": tenant_id},
        "subscription_data": {"metadata": {"tenant_id": tenant_id}},
    }
    existing = ex.get("stripe_customer_id")
    if existing:
        params["customer"] = str(existing)
    else:
        params["customer_creation"] = "always"
    sess = stripe.checkout.Session.create(**params)
    url = sess.url if hasattr(sess, "url") else sess.get("url")
    if not url:
        raise RuntimeError("Stripe Checkout Session missing url")
    return str(url)


def create_portal_session_url(*, tenant_id: str) -> str:
    configure_stripe()
    import stripe

    row = tenants_db.get_tenant(tenant_id)
    if not row or not row.get("stripe_customer_id"):
        raise ValueError("No Stripe customer linked; complete subscription checkout first.")
    sess = stripe.billing_portal.Session.create(
        customer=str(row["stripe_customer_id"]),
        return_url=billing_portal_return_url(),
    )
    url = sess.url if hasattr(sess, "url") else sess.get("url")
    if not url:
        raise RuntimeError("Stripe billing portal session missing url")
    return str(url)


def billing_catalog_public_flags() -> dict[str, Any]:
    """Safe to expose to browser (no secrets)."""
    has_key = bool(stripe_secret_key())
    indie = bool(price_id_for_tier("indie"))
    team = bool(price_id_for_tier("team"))
    return {
        "stripe_checkout_available": has_key and (indie or team),
        "checkout_tiers": [t for t in ("indie", "team") if price_id_for_tier(t)],
        "portal_needs_customer": True,
    }
