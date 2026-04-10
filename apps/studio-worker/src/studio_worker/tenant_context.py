from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Header, HTTPException

from studio_worker.tenants_db import resolve_api_key
from studio_worker.tiers import Tier, get_tier

# Stable synthetic id for local dev when API keys are not required (not stored in tenants DB).
DEV_TENANT_ID = "00000000-0000-0000-0000-000000000001"


@dataclass
class RequestTenant:
    """Resolved tenant for one HTTP request (or dev bypass)."""

    tenant_id: str
    tier: Tier
    tier_id: str
    limits_enforced: bool
    """When False (local dev), skip credits, concurrency, and tier texture gate."""
    credits_precharged: bool = False
    """Queue path: credits were consumed at enqueue; worker only acquires a slot."""


def api_auth_required() -> bool:
    """When true, all studio API routes except health/comfy-status require a valid API key."""
    return os.environ.get("STUDIO_API_AUTH_REQUIRED", "").lower() in ("1", "true", "yes")


def api_auth_disabled() -> bool:
    """True in default local mode (no API keys)."""
    return not api_auth_required()


def resolve_request_tenant(
    *,
    authorization: str | None,
    x_api_key: str | None,
) -> RequestTenant:
    if not api_auth_required():
        return RequestTenant(
            tenant_id=DEV_TENANT_ID,
            tier=get_tier("dev"),
            tier_id="dev",
            limits_enforced=False,
            credits_precharged=False,
        )
    raw: str | None = None
    if x_api_key and str(x_api_key).strip():
        raw = str(x_api_key).strip()
    elif authorization:
        auth = authorization.strip()
        if auth.lower().startswith("bearer "):
            raw = auth[7:].strip()
    if not raw:
        raise PermissionError(
            "API key required. Send header Authorization: Bearer <key> or X-API-Key (from immersive-studio tenants issue-key)."
        )
    info = resolve_api_key(raw)
    if info is None:
        raise PermissionError("Invalid or revoked API key.")
    tid = str(info["tenant_id"])
    t_id = str(info["tier_id"])
    tier = get_tier(t_id)
    return RequestTenant(
        tenant_id=tid,
        tier=tier,
        tier_id=t_id,
        limits_enforced=True,
        credits_precharged=False,
    )


def get_request_tenant(
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> RequestTenant:
    try:
        return resolve_request_tenant(authorization=authorization, x_api_key=x_api_key)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
