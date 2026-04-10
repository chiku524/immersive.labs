"""
Tenants / API keys / billing counters: SQLite file (default) or Postgres (`STUDIO_TENANTS_BACKEND=postgres` + `DATABASE_URL`).

Key hashing helpers always live in `tenants_sqlite` (no DB). Postgres backend is loaded lazily.
"""

from __future__ import annotations

from studio_worker.scale_config import tenants_backend
from studio_worker.tenants_sqlite import generate_api_key_raw, hash_api_key

if tenants_backend() == "postgres":
    from studio_worker import tenants_postgres as _tb

    init_tenants_schema = _tb.init_tenants_schema
    create_tenant = _tb.create_tenant
    create_api_key = _tb.create_api_key
    resolve_api_key = _tb.resolve_api_key
    list_tenants = _tb.list_tenants
    get_tenant = _tb.get_tenant
    find_tenant_by_stripe_customer = _tb.find_tenant_by_stripe_customer
    link_stripe_customer = _tb.link_stripe_customer
    set_stripe_subscription_id = _tb.set_stripe_subscription_id
    set_tenant_tier = _tb.set_tenant_tier
    get_usage_row = _tb.get_usage_row
    try_consume_credits = _tb.try_consume_credits
    refund_credits = _tb.refund_credits
    try_acquire_job_slot = _tb.try_acquire_job_slot
    release_job_slot = _tb.release_job_slot
    tenant_count = _tb.tenant_count
else:
    from studio_worker import tenants_sqlite as _tb

    init_tenants_schema = _tb.init_tenants_schema
    create_tenant = _tb.create_tenant
    create_api_key = _tb.create_api_key
    resolve_api_key = _tb.resolve_api_key
    list_tenants = _tb.list_tenants
    get_tenant = _tb.get_tenant
    find_tenant_by_stripe_customer = _tb.find_tenant_by_stripe_customer
    link_stripe_customer = _tb.link_stripe_customer
    set_stripe_subscription_id = _tb.set_stripe_subscription_id
    set_tenant_tier = _tb.set_tenant_tier
    get_usage_row = _tb.get_usage_row
    try_consume_credits = _tb.try_consume_credits
    refund_credits = _tb.refund_credits
    try_acquire_job_slot = _tb.try_acquire_job_slot
    release_job_slot = _tb.release_job_slot
    tenant_count = _tb.tenant_count

__all__ = [
    "create_api_key",
    "create_tenant",
    "find_tenant_by_stripe_customer",
    "generate_api_key_raw",
    "get_tenant",
    "get_usage_row",
    "hash_api_key",
    "init_tenants_schema",
    "link_stripe_customer",
    "list_tenants",
    "refund_credits",
    "release_job_slot",
    "resolve_api_key",
    "set_stripe_subscription_id",
    "set_tenant_tier",
    "tenant_count",
    "try_acquire_job_slot",
    "try_consume_credits",
]
