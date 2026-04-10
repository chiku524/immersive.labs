"""Postgres-backed tenants, API keys, usage, and concurrency slots (shared across replicas)."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from studio_worker.scale_config import database_url
from studio_worker.tiers import get_tier
from studio_worker.tenants_sqlite import generate_api_key_raw, hash_api_key

_lock = threading.Lock()


def _utc_period() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m")


def _connect() -> psycopg.Connection:
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is required for Postgres tenants backend")
    return psycopg.connect(url, autocommit=False)


def init_tenants_schema() -> None:
    with _lock:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tenants (
                      id TEXT PRIMARY KEY,
                      name TEXT NOT NULL,
                      tier_id TEXT NOT NULL,
                      created_at TEXT NOT NULL,
                      stripe_customer_id TEXT,
                      stripe_subscription_id TEXT
                    );

                    CREATE TABLE IF NOT EXISTS api_keys (
                      id TEXT PRIMARY KEY,
                      tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                      key_hash TEXT NOT NULL UNIQUE,
                      label TEXT,
                      created_at TEXT NOT NULL,
                      revoked_at TEXT
                    );

                    CREATE TABLE IF NOT EXISTS usage_monthly (
                      tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                      period TEXT NOT NULL,
                      credits_used INTEGER NOT NULL DEFAULT 0,
                      PRIMARY KEY (tenant_id, period)
                    );

                    CREATE TABLE IF NOT EXISTS tenant_runtime (
                      tenant_id TEXT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
                      running_jobs INTEGER NOT NULL DEFAULT 0
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ux_tenants_stripe_customer
                    ON tenants(stripe_customer_id)
                    WHERE stripe_customer_id IS NOT NULL
                    """
                )
            conn.commit()


def create_tenant(*, name: str, tier_id: str) -> str:
    init_tenants_schema()
    tid = str(uuid.uuid4())
    now = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with _lock:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tenants (id, name, tier_id, created_at) VALUES (%s, %s, %s, %s)",
                    (tid, name[:200], tier_id, now),
                )
                cur.execute(
                    "INSERT INTO tenant_runtime (tenant_id, running_jobs) VALUES (%s, 0) ON CONFLICT DO NOTHING",
                    (tid,),
                )
            conn.commit()
    return tid


def create_api_key(*, tenant_id: str, label: str | None = None) -> str:
    init_tenants_schema()
    raw = generate_api_key_raw()
    kid = str(uuid.uuid4())
    now = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    h = hash_api_key(raw)
    with _lock:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO api_keys (id, tenant_id, key_hash, label, created_at, revoked_at)
                    VALUES (%s, %s, %s, %s, %s, NULL)
                    """,
                    (kid, tenant_id, h, (label or "")[:120] or None, now),
                )
            conn.commit()
    return raw


def resolve_api_key(raw_key: str) -> dict[str, Any] | None:
    if not raw_key or not raw_key.strip():
        return None
    init_tenants_schema()
    h = hash_api_key(raw_key.strip())
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT k.id AS key_id, k.tenant_id, t.tier_id
                    FROM api_keys k
                    JOIN tenants t ON t.id = k.tenant_id
                    WHERE k.key_hash = %s AND k.revoked_at IS NULL
                    """,
                    (h,),
                )
                row = cur.fetchone()
            conn.commit()
    if row is None:
        return None
    return {"key_id": str(row["key_id"]), "tenant_id": str(row["tenant_id"]), "tier_id": str(row["tier_id"])}


def list_tenants() -> list[dict[str, Any]]:
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, name, tier_id, created_at, stripe_customer_id, stripe_subscription_id
                    FROM tenants ORDER BY created_at ASC
                    """
                )
                rows = cur.fetchall()
            conn.commit()
    return [dict(r) for r in rows]


def get_tenant(tenant_id: str) -> dict[str, Any] | None:
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, name, tier_id, created_at, stripe_customer_id, stripe_subscription_id
                    FROM tenants WHERE id = %s
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
            conn.commit()
    return dict(row) if row else None


def find_tenant_by_stripe_customer(stripe_customer_id: str) -> dict[str, Any] | None:
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, name, tier_id, created_at, stripe_customer_id, stripe_subscription_id
                    FROM tenants WHERE stripe_customer_id = %s
                    """,
                    (stripe_customer_id,),
                )
                row = cur.fetchone()
            conn.commit()
    return dict(row) if row else None


def link_stripe_customer(tenant_id: str, stripe_customer_id: str) -> None:
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tenants SET stripe_customer_id = %s WHERE id = %s",
                    (stripe_customer_id, tenant_id),
                )
                if cur.rowcount != 1:
                    raise ValueError("Unknown tenant_id")
            conn.commit()


def set_stripe_subscription_id(tenant_id: str, subscription_id: str | None) -> None:
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tenants SET stripe_subscription_id = %s WHERE id = %s",
                    (subscription_id, tenant_id),
                )
                if cur.rowcount != 1:
                    raise ValueError("Unknown tenant_id")
            conn.commit()


def set_tenant_tier(tenant_id: str, tier_id: str) -> None:
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE tenants SET tier_id = %s WHERE id = %s", (tier_id, tenant_id))
                if cur.rowcount != 1:
                    raise ValueError("Unknown tenant_id")
            conn.commit()


def get_usage_row(tenant_id: str, period: str | None = None) -> tuple[int, str]:
    period = period or _utc_period()
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT credits_used FROM usage_monthly WHERE tenant_id = %s AND period = %s",
                    (tenant_id, period),
                )
                row = cur.fetchone()
            conn.commit()
    used = int(row["credits_used"]) if row else 0
    return used, period


def try_consume_credits(tenant_id: str, cost: int, *, period: str | None = None) -> tuple[int, str]:
    if cost <= 0:
        return get_usage_row(tenant_id, period)
    period = period or _utc_period()
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            try:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT tier_id FROM tenants WHERE id = %s FOR UPDATE",
                        (tenant_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        conn.rollback()
                        raise ValueError("Unknown tenant")
                    tier = get_tier(str(row["tier_id"]))
                    cap = tier.monthly_credits
                    cur.execute(
                        """
                        SELECT credits_used FROM usage_monthly
                        WHERE tenant_id = %s AND period = %s FOR UPDATE
                        """,
                        (tenant_id, period),
                    )
                    urow = cur.fetchone()
                    used = int(urow["credits_used"]) if urow else 0
                    if used + cost > cap:
                        conn.rollback()
                        raise ValueError(
                            f"Monthly credit limit reached for tier '{tier.display_name}' "
                            f"({used}/{cap} used this period). Upgrade or wait for the next billing period."
                        )
                    cur.execute(
                        """
                        INSERT INTO usage_monthly (tenant_id, period, credits_used)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (tenant_id, period) DO UPDATE SET
                          credits_used = usage_monthly.credits_used + EXCLUDED.credits_used
                        """,
                        (tenant_id, period, cost),
                    )
                    cur.execute(
                        "SELECT credits_used FROM usage_monthly WHERE tenant_id = %s AND period = %s",
                        (tenant_id, period),
                    )
                    nrow = cur.fetchone()
                    new_total = int(nrow["credits_used"]) if nrow else used + cost
                conn.commit()
                return new_total, period
            except Exception:
                conn.rollback()
                raise


def refund_credits(tenant_id: str, cost: int, *, period: str | None = None) -> None:
    if cost <= 0:
        return
    period = period or _utc_period()
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            try:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT credits_used FROM usage_monthly
                        WHERE tenant_id = %s AND period = %s FOR UPDATE
                        """,
                        (tenant_id, period),
                    )
                    urow = cur.fetchone()
                    if not urow:
                        conn.rollback()
                        return
                    used = int(urow["credits_used"])
                    new_used = max(0, used - cost)
                    cur.execute(
                        "UPDATE usage_monthly SET credits_used = %s WHERE tenant_id = %s AND period = %s",
                        (new_used, tenant_id, period),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise


def try_acquire_job_slot(tenant_id: str, max_concurrent: int) -> None:
    if max_concurrent < 1:
        max_concurrent = 1
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO tenant_runtime (tenant_id, running_jobs)
                        VALUES (%s, 0)
                        ON CONFLICT (tenant_id) DO NOTHING
                        """,
                        (tenant_id,),
                    )
                    cur.execute(
                        """
                        UPDATE tenant_runtime
                        SET running_jobs = running_jobs + 1
                        WHERE tenant_id = %s AND running_jobs < %s
                        """,
                        (tenant_id, max_concurrent),
                    )
                    if cur.rowcount != 1:
                        conn.rollback()
                        raise ValueError(
                            f"Too many concurrent jobs for this workspace (max {max_concurrent}). "
                            "Wait for a job to finish or upgrade your tier."
                        )
                conn.commit()
            except ValueError:
                raise
            except Exception:
                conn.rollback()
                raise


def release_job_slot(tenant_id: str) -> None:
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tenant_runtime
                    SET running_jobs = CASE WHEN running_jobs > 0 THEN running_jobs - 1 ELSE 0 END
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
            conn.commit()


def tenant_count() -> int:
    init_tenants_schema()
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT COUNT(*) AS c FROM tenants")
                row = cur.fetchone()
            conn.commit()
    return int(row["c"]) if row else 0
