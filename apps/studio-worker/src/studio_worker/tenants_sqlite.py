from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

import studio_worker.paths as _paths
from studio_worker.tiers import get_tier

_lock = threading.Lock()


def _utc_period() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m")


def _connect() -> sqlite3.Connection:
    path = _paths.tenants_db_path()
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_tenants_schema() -> None:
    with _lock:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  tier_id TEXT NOT NULL,
                  created_at TEXT NOT NULL
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
            cols = {r[1] for r in conn.execute("PRAGMA table_info(tenants)").fetchall()}
            if "stripe_customer_id" not in cols:
                conn.execute("ALTER TABLE tenants ADD COLUMN stripe_customer_id TEXT")
            if "stripe_subscription_id" not in cols:
                conn.execute("ALTER TABLE tenants ADD COLUMN stripe_subscription_id TEXT")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_tenants_stripe_customer "
                "ON tenants(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL"
            )
            conn.commit()
        finally:
            conn.close()


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_key_raw() -> str:
    return "sk_il_" + secrets.token_hex(24)


def create_tenant(*, name: str, tier_id: str) -> str:
    init_tenants_schema()
    tid = str(uuid.uuid4())
    now = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO tenants (id, name, tier_id, created_at) VALUES (?, ?, ?, ?)",
                (tid, name[:200], tier_id, now),
            )
            conn.execute(
                "INSERT INTO tenant_runtime (tenant_id, running_jobs) VALUES (?, 0)",
                (tid,),
            )
            conn.commit()
        finally:
            conn.close()
    return tid


def create_api_key(*, tenant_id: str, label: str | None = None) -> str:
    """Returns the raw key once (store nowhere else)."""
    init_tenants_schema()
    raw = generate_api_key_raw()
    kid = str(uuid.uuid4())
    now = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    h = hash_api_key(raw)
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO api_keys (id, tenant_id, key_hash, label, created_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (kid, tenant_id, h, (label or "")[:120] or None, now),
            )
            conn.commit()
        finally:
            conn.close()
    return raw


def resolve_api_key(raw_key: str) -> dict[str, Any] | None:
    """Return dict with tenant_id, tier_id, key_id or None if invalid/revoked."""
    if not raw_key or not raw_key.strip():
        return None
    init_tenants_schema()
    h = hash_api_key(raw_key.strip())
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT k.id AS key_id, k.tenant_id, t.tier_id
                FROM api_keys k
                JOIN tenants t ON t.id = k.tenant_id
                WHERE k.key_hash = ? AND k.revoked_at IS NULL
                """,
                (h,),
            ).fetchone()
            if row is None:
                return None
            return {"key_id": str(row["key_id"]), "tenant_id": str(row["tenant_id"]), "tier_id": str(row["tier_id"])}
        finally:
            conn.close()


def list_tenants() -> list[dict[str, Any]]:
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT id, name, tier_id, created_at, stripe_customer_id, stripe_subscription_id
                FROM tenants ORDER BY created_at ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_tenant(tenant_id: str) -> dict[str, Any] | None:
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT id, name, tier_id, created_at, stripe_customer_id, stripe_subscription_id
                FROM tenants WHERE id = ?
                """,
                (tenant_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def find_tenant_by_stripe_customer(stripe_customer_id: str) -> dict[str, Any] | None:
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT id, name, tier_id, created_at, stripe_customer_id, stripe_subscription_id
                FROM tenants WHERE stripe_customer_id = ?
                """,
                (stripe_customer_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def link_stripe_customer(tenant_id: str, stripe_customer_id: str) -> None:
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE tenants SET stripe_customer_id = ? WHERE id = ?",
                (stripe_customer_id, tenant_id),
            )
            if conn.total_changes != 1:
                raise ValueError("Unknown tenant_id")
            conn.commit()
        finally:
            conn.close()


def set_stripe_subscription_id(tenant_id: str, subscription_id: str | None) -> None:
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE tenants SET stripe_subscription_id = ? WHERE id = ?",
                (subscription_id, tenant_id),
            )
            if conn.total_changes != 1:
                raise ValueError("Unknown tenant_id")
            conn.commit()
        finally:
            conn.close()


def set_tenant_tier(tenant_id: str, tier_id: str) -> None:
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            conn.execute("UPDATE tenants SET tier_id = ? WHERE id = ?", (tier_id, tenant_id))
            if conn.total_changes != 1:
                raise ValueError("Unknown tenant_id")
            conn.commit()
        finally:
            conn.close()


def get_usage_row(tenant_id: str, period: str | None = None) -> tuple[int, str]:
    period = period or _utc_period()
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT credits_used FROM usage_monthly WHERE tenant_id = ? AND period = ?",
                (tenant_id, period),
            ).fetchone()
            used = int(row["credits_used"]) if row else 0
            return used, period
        finally:
            conn.close()


def try_consume_credits(tenant_id: str, cost: int, *, period: str | None = None) -> tuple[int, str]:
    """
    Atomically increment credits_used if tier allows. Returns (new_total, period).
    Raises ValueError on insufficient quota.
    """
    if cost <= 0:
        return get_usage_row(tenant_id, period)
    period = period or _utc_period()
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT tier_id FROM tenants WHERE id = ?", (tenant_id,)
            ).fetchone()
            if row is None:
                conn.rollback()
                raise ValueError("Unknown tenant")
            tier = get_tier(str(row["tier_id"]))
            cap = tier.monthly_credits
            urow = conn.execute(
                "SELECT credits_used FROM usage_monthly WHERE tenant_id = ? AND period = ?",
                (tenant_id, period),
            ).fetchone()
            used = int(urow["credits_used"]) if urow else 0
            if used + cost > cap:
                conn.rollback()
                raise ValueError(
                    f"Monthly credit limit reached for tier '{tier.display_name}' "
                    f"({used}/{cap} used this period). Upgrade or wait for the next billing period."
                )
            conn.execute(
                """
                INSERT INTO usage_monthly (tenant_id, period, credits_used)
                VALUES (?, ?, ?)
                ON CONFLICT(tenant_id, period) DO UPDATE SET
                  credits_used = usage_monthly.credits_used + excluded.credits_used
                """,
                (tenant_id, period, cost),
            )
            nrow = conn.execute(
                "SELECT credits_used FROM usage_monthly WHERE tenant_id = ? AND period = ?",
                (tenant_id, period),
            ).fetchone()
            new_total = int(nrow["credits_used"]) if nrow else used + cost
            conn.commit()
            return new_total, period
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def refund_credits(tenant_id: str, cost: int, *, period: str | None = None) -> None:
    """Decrement credits_used (floor at 0). Used when enqueue deduplicates after credits were charged."""
    if cost <= 0:
        return
    period = period or _utc_period()
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            urow = conn.execute(
                "SELECT credits_used FROM usage_monthly WHERE tenant_id = ? AND period = ?",
                (tenant_id, period),
            ).fetchone()
            if not urow:
                conn.rollback()
                return
            used = int(urow["credits_used"])
            new_used = max(0, used - cost)
            conn.execute(
                "UPDATE usage_monthly SET credits_used = ? WHERE tenant_id = ? AND period = ?",
                (new_used, tenant_id, period),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def try_acquire_job_slot(tenant_id: str, max_concurrent: int) -> None:
    if max_concurrent < 1:
        max_concurrent = 1
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT OR IGNORE INTO tenant_runtime (tenant_id, running_jobs) VALUES (?, 0)",
                (tenant_id,),
            )
            cur = conn.execute(
                """
                UPDATE tenant_runtime
                SET running_jobs = running_jobs + 1
                WHERE tenant_id = ? AND running_jobs < ?
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
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def release_job_slot(tenant_id: str) -> None:
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE tenant_runtime
                SET running_jobs = CASE WHEN running_jobs > 0 THEN running_jobs - 1 ELSE 0 END
                WHERE tenant_id = ?
                """,
                (tenant_id,),
            )
            conn.commit()
        finally:
            conn.close()


def tenant_count() -> int:
    init_tenants_schema()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS c FROM tenants").fetchone()
            return int(row["c"]) if row else 0
        finally:
            conn.close()
