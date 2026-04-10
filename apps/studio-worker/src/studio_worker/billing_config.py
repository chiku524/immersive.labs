from __future__ import annotations

import os
from typing import Any


def stripe_secret_key() -> str:
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()


def stripe_webhook_secret() -> str:
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()


def trial_end_notify_webhook_url() -> str:
    """Optional POST target when customer.subscription.trial_will_end fires (Zapier, Slack, etc.)."""
    return os.environ.get("STUDIO_TRIAL_END_NOTIFY_WEBHOOK_URL", "").strip()


def stripe_api_version() -> str | None:
    v = os.environ.get("STRIPE_API_VERSION", "").strip()
    return v or None


def billing_success_url() -> str:
    return os.environ.get(
        "STUDIO_BILLING_SUCCESS_URL",
        "http://127.0.0.1:5173/studio?billing=success",
    ).strip()


def billing_cancel_url() -> str:
    return os.environ.get(
        "STUDIO_BILLING_CANCEL_URL",
        "http://127.0.0.1:5173/studio?billing=cancel",
    ).strip()


def billing_portal_return_url() -> str:
    return os.environ.get(
        "STUDIO_BILLING_PORTAL_RETURN_URL",
        "http://127.0.0.1:5173/studio",
    ).strip()


def price_id_for_tier(tier: str) -> str | None:
    tier = tier.lower().strip()
    if tier == "indie":
        return os.environ.get("STUDIO_STRIPE_PRICE_INDIE", "").strip() or None
    if tier == "team":
        return os.environ.get("STUDIO_STRIPE_PRICE_TEAM", "").strip() or None
    return None


def _price_map_from_env() -> dict[str, str]:
    """
    Optional: STUDIO_STRIPE_PRICE_MAP=price_abc:indie,price_def:team,price_ghi:free
    (later entries override earlier for same price id)
    """
    raw = os.environ.get("STUDIO_STRIPE_PRICE_MAP", "").strip()
    out: dict[str, str] = {}
    if not raw:
        return out
    for part in raw.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        pid, tid = part.split(":", 1)
        pid, tid = pid.strip(), tid.strip().lower()
        if pid and tid in ("free", "indie", "team"):
            out[pid] = tid
    return out


def tier_for_stripe_price_id(price_id: str | None) -> str | None:
    if not price_id:
        return None
    m = _price_map_from_env()
    if price_id in m:
        return m[price_id]
    indie = os.environ.get("STUDIO_STRIPE_PRICE_INDIE", "").strip()
    team = os.environ.get("STUDIO_STRIPE_PRICE_TEAM", "").strip()
    if indie and price_id == indie:
        return "indie"
    if team and price_id == team:
        return "team"
    return None


def tier_from_price_metadata(price: Any) -> str | None:
    """Use Stripe Price.metadata.tier when set (dashboard or API)."""
    try:
        if isinstance(price, dict):
            meta = price.get("metadata") or {}
        else:
            m = getattr(price, "metadata", None)
            meta = dict(m) if m is not None else {}
        t = str(meta.get("tier", "")).strip().lower()
        if t in ("free", "indie", "team"):
            return t
    except Exception:
        pass
    return None


def resolve_tier_for_price(price: Any) -> str | None:
    from_meta = tier_from_price_metadata(price)
    if from_meta:
        return from_meta
    pid = price.get("id") if isinstance(price, dict) else getattr(price, "id", None)
    return tier_for_stripe_price_id(str(pid) if pid else None)
