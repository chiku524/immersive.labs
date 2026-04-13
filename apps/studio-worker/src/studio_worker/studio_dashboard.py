"""
Shared JSON payloads for /studio: one GET bundles usage + billing + jobs to cut tunnel round-trips.
"""

from __future__ import annotations

from typing import Any

from studio_worker import tenants_db
from studio_worker.jobs_store import list_jobs
from studio_worker.paths import jobs_root
from studio_worker.stripe_billing import billing_catalog_public_flags
from studio_worker.tenant_context import RequestTenant
from studio_worker.tiers import (
    CREDIT_COST_GENERATE_SPEC,
    CREDIT_COST_RUN_JOB,
    CREDIT_COST_RUN_JOB_TEXTURES,
)


def usage_dict(tenant: RequestTenant) -> dict[str, Any]:
    if not tenant.limits_enforced:
        return {
            "limits_enforced": False,
            "tier_id": tenant.tier_id,
            "tier_name": tenant.tier.display_name,
            "period": None,
            "credits_used": 0,
            "credits_cap": None,
            "credits_generate_spec": CREDIT_COST_GENERATE_SPEC,
            "credits_run_job": CREDIT_COST_RUN_JOB,
            "credits_run_job_textures": CREDIT_COST_RUN_JOB_TEXTURES,
            "textures_allowed": True,
            "max_concurrent_jobs": None,
        }
    used, period = tenants_db.get_usage_row(tenant.tenant_id)
    return {
        "limits_enforced": True,
        "tier_id": tenant.tier_id,
        "tier_name": tenant.tier.display_name,
        "period": period,
        "credits_used": used,
        "credits_cap": tenant.tier.monthly_credits,
        "credits_generate_spec": CREDIT_COST_GENERATE_SPEC,
        "credits_run_job": CREDIT_COST_RUN_JOB,
        "credits_run_job_textures": CREDIT_COST_RUN_JOB_TEXTURES,
        "textures_allowed": tenant.tier.textures_allowed,
        "max_concurrent_jobs": tenant.tier.max_concurrent_jobs,
    }


def billing_status_dict(tenant: RequestTenant) -> dict[str, Any]:
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


def jobs_list_dict(tenant: RequestTenant) -> dict[str, Any]:
    return {
        "jobs": list_jobs(
            tenant_id=tenant.tenant_id,
            include_legacy_unscoped=not tenant.limits_enforced,
        ),
        "jobs_root": str(jobs_root().resolve()),
    }


def studio_dashboard_dict(tenant: RequestTenant) -> dict[str, Any]:
    return {
        "usage": usage_dict(tenant),
        "billing": billing_status_dict(tenant),
        "jobs": jobs_list_dict(tenant),
    }
