from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from typing import NamedTuple
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from studio_worker.paths import queue_db_path

# init_schema runs once per queue_db_path() (tests swap tmp paths; production path is stable).
_schema_init_lock = threading.Lock()
_queue_schema_initialized_for: str | None = None
# Serialize enqueue / claim / mark_* so they never share a connection with concurrent readers.
_write_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _connect() -> sqlite3.Connection:
    path: Path = queue_db_path()
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_schema() -> None:
    global _queue_schema_initialized_for
    path_key = str(queue_db_path().resolve())
    with _schema_init_lock:
        if _queue_schema_initialized_for == path_key:
            return
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS queue_jobs (
                  id TEXT PRIMARY KEY,
                  status TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0,
                  max_attempts INTEGER NOT NULL DEFAULT 3,
                  last_error TEXT,
                  result_json TEXT,
                  studio_job_id TEXT,
                  worker_id TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_queue_status_created
                  ON queue_jobs (status, created_at);
                """
            )
            cols = {r[1] for r in conn.execute("PRAGMA table_info(queue_jobs)").fetchall()}
            if "tenant_id" not in cols:
                conn.execute("ALTER TABLE queue_jobs ADD COLUMN tenant_id TEXT")
            if "idempotency_key" not in cols:
                conn.execute("ALTER TABLE queue_jobs ADD COLUMN idempotency_key TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_queue_tenant_created ON queue_jobs (tenant_id, created_at)"
            )
            conn.execute("DROP INDEX IF EXISTS idx_queue_idempotency")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_idempotency
                ON queue_jobs (coalesce(tenant_id, ''), idempotency_key)
                WHERE idempotency_key IS NOT NULL AND trim(idempotency_key) != ''
                """
            )
            conn.commit()
        finally:
            conn.close()
        _queue_schema_initialized_for = path_key


class EnqueueOutcome(NamedTuple):
    queue_id: str
    deduplicated: bool


def count_queue_by_status(
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> dict[str, int]:
    """Count queue rows per status; optional tenant filter (matches list_queue_jobs semantics)."""
    init_schema()
    counts: dict[str, int] = {}
    conn = _connect()
    try:
        if tenant_id is None:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM queue_jobs GROUP BY status"
            ).fetchall()
        elif include_legacy_unscoped:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS c FROM queue_jobs
                WHERE tenant_id = ? OR tenant_id IS NULL
                GROUP BY status
                """,
                (tenant_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS c FROM queue_jobs
                WHERE tenant_id = ?
                GROUP BY status
                """,
                (tenant_id,),
            ).fetchall()
        for r in rows:
            counts[str(r["status"])] = int(r["c"])
        return counts
    finally:
        conn.close()


def _age_seconds_from_created_at(created_at: str) -> float | None:
    """Parse queue job ISO timestamp (with Z) to age in seconds."""
    raw = (created_at or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        started = datetime.fromisoformat(raw)
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        return max(0.0, (datetime.now(tz=UTC) - started).total_seconds())
    except ValueError:
        return None


def _tenant_where_sql(
    tenant_id: str | None, include_legacy_unscoped: bool
) -> tuple[str, list[Any]]:
    if tenant_id is None:
        return "", []
    if include_legacy_unscoped:
        return " AND (tenant_id = ? OR tenant_id IS NULL)", [tenant_id]
    return " AND tenant_id = ?", [tenant_id]


def queue_slo_hints(
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> dict[str, Any]:
    """
    Lightweight SLO fields for metrics / alerting (SQLite queue only).
    ``pending_oldest_age_seconds``: oldest *claimable* pending row (attempts < max_attempts).
    """
    init_schema()
    tw, tparams = _tenant_where_sql(tenant_id, include_legacy_unscoped)
    conn = _connect()
    try:
        row_p = conn.execute(
            f"""
            SELECT created_at FROM queue_jobs
            WHERE status = 'pending' AND attempts < max_attempts{tw}
            ORDER BY datetime(created_at) ASC LIMIT 1
            """,
            tparams,
        ).fetchone()
        pending_oldest = None
        if row_p and row_p["created_at"]:
            pending_oldest = _age_seconds_from_created_at(str(row_p["created_at"]))

        row_r = conn.execute(
            f"""
            SELECT updated_at FROM queue_jobs
            WHERE status = 'running'{tw}
            ORDER BY datetime(updated_at) ASC LIMIT 1
            """,
            tparams,
        ).fetchone()
        running_oldest = None
        if row_r and row_r["updated_at"]:
            running_oldest = _age_seconds_from_created_at(str(row_r["updated_at"]))

        row_pc = conn.execute(
            f"""
            SELECT COUNT(*) AS c FROM queue_jobs
            WHERE status = 'pending' AND attempts < max_attempts{tw}
            """,
            tparams,
        ).fetchone()
        pending_claimable = int(row_pc["c"]) if row_pc else 0

        row_rc = conn.execute(
            f"SELECT COUNT(*) AS c FROM queue_jobs WHERE status = 'running'{tw}",
            tparams,
        ).fetchone()
        running_count = int(row_rc["c"]) if row_rc else 0

        return {
            "pending_oldest_age_seconds": pending_oldest,
            "running_oldest_age_seconds": running_oldest,
            "pending_claimable_count": pending_claimable,
            "running_count": running_count,
        }
    finally:
        conn.close()


def find_queue_id_by_idempotency(tenant_id: str | None, idempotency_key: str) -> str | None:
    """Return existing queue job id for this tenant + key, or None."""
    if not idempotency_key.strip():
        return None
    init_schema()
    tid_coalesce = "" if tenant_id is None else str(tenant_id)
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT id FROM queue_jobs
            WHERE coalesce(tenant_id, '') = ? AND idempotency_key = ?
            LIMIT 1
            """,
            (tid_coalesce, idempotency_key.strip()),
        ).fetchone()
        return str(row["id"]) if row else None
    finally:
        conn.close()


def enqueue_job(
    payload: dict[str, Any],
    *,
    max_attempts: int = 3,
    queue_id: str | None = None,
    tenant_id: str | None = None,
    idempotency_key: str | None = None,
) -> EnqueueOutcome:
    init_schema()
    qid = queue_id or str(uuid.uuid4())
    now = _utc_now()
    max_attempts = max(1, int(max_attempts))
    tid = tenant_id if tenant_id is not None else payload.get("tenant_id")
    tid_s = str(tid) if tid is not None else None
    idem = (idempotency_key or "").strip()[:128] or None
    tid_coalesce = "" if tid_s is None else str(tid_s)
    with _write_lock:
        conn = _connect()
        try:
            try:
                conn.execute(
                    """
                    INSERT INTO queue_jobs (
                      id, status, payload, attempts, max_attempts,
                      last_error, result_json, studio_job_id, worker_id, created_at, updated_at,
                      tenant_id, idempotency_key
                    ) VALUES (?, 'pending', ?, 0, ?, NULL, NULL, NULL, NULL, ?, ?, ?, ?)
                    """,
                    (qid, json.dumps(payload), max_attempts, now, now, tid_s, idem),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                conn.rollback()
                # Same connection — avoid nested find_queue_id… (would deadlock with _write_lock).
                row = conn.execute(
                    """
                    SELECT id FROM queue_jobs
                    WHERE coalesce(tenant_id, '') = ? AND idempotency_key = ?
                    LIMIT 1
                    """,
                    (tid_coalesce, (idem or "").strip()),
                ).fetchone()
                if row:
                    return EnqueueOutcome(str(row["id"]), True)
                raise
        finally:
            conn.close()
    return EnqueueOutcome(qid, False)


def claim_next_job(*, worker_id: str) -> dict[str, Any] | None:
    """Atomically claim the oldest pending job with attempts remaining."""
    init_schema()
    now = _utc_now()
    with _write_lock:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id, payload, attempts, max_attempts
                FROM queue_jobs
                WHERE status = 'pending' AND attempts < max_attempts
                ORDER BY datetime(created_at) ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            qid = str(row["id"])
            attempts = int(row["attempts"]) + 1
            cur = conn.execute(
                """
                UPDATE queue_jobs
                SET status = 'running', attempts = ?, worker_id = ?, updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (attempts, worker_id, now, qid),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return None
            conn.commit()
            payload = json.loads(row["payload"])
            return {
                "id": qid,
                "payload": payload,
                "attempts": attempts,
                "max_attempts": int(row["max_attempts"]),
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def mark_completed(
    queue_id: str,
    *,
    result: dict[str, Any],
    studio_job_id: str | None,
) -> None:
    now = _utc_now()
    with _write_lock:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE queue_jobs
                SET status = 'completed',
                    result_json = ?,
                    studio_job_id = ?,
                    last_error = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(result), studio_job_id, now, queue_id),
            )
            conn.commit()
        finally:
            conn.close()


def mark_failed(queue_id: str, *, error: str, attempts: int, max_attempts: int) -> str:
    """
    Mark job failed. Returns new status: 'pending' (retry) or 'dead'.
    """
    now = _utc_now()
    err = error[:4000]
    if attempts >= max_attempts:
        status = "dead"
    else:
        status = "pending"
    with _write_lock:
        conn = _connect()
        try:
            clear_idem = "1" if status == "dead" else "0"
            conn.execute(
                """
                UPDATE queue_jobs
                SET status = ?,
                    last_error = ?,
                    worker_id = NULL,
                    updated_at = ?,
                    idempotency_key = CASE WHEN ? = '1' THEN NULL ELSE idempotency_key END
                WHERE id = ?
                """,
                (status, err, now, clear_idem, queue_id),
            )
            conn.commit()
        finally:
            conn.close()
    return status


def get_queue_job(
    queue_id: str,
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> dict[str, Any] | None:
    init_schema()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM queue_jobs WHERE id = ?", (queue_id,)
        ).fetchone()
        if row is None:
            return None
        d = _row_to_dict(row)
        if tenant_id is not None:
            row_tid = d.get("tenant_id")
            if row_tid != tenant_id and not (
                include_legacy_unscoped and row_tid is None
            ):
                return None
        return d
    finally:
        conn.close()


def list_queue_jobs(
    *,
    limit: int = 50,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> list[dict[str, Any]]:
    init_schema()
    limit = max(1, min(limit, 500))
    conn = _connect()
    try:
        if tenant_id is None:
            rows = conn.execute(
                """
                SELECT * FROM queue_jobs
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            if include_legacy_unscoped:
                rows = conn.execute(
                    """
                    SELECT * FROM queue_jobs
                    WHERE tenant_id = ? OR tenant_id IS NULL
                    ORDER BY datetime(created_at) DESC
                    LIMIT ?
                    """,
                    (tenant_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM queue_jobs
                    WHERE tenant_id = ?
                    ORDER BY datetime(created_at) DESC
                    LIMIT ?
                    """,
                    (tenant_id, limit),
                ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("payload"):
        try:
            d["payload"] = json.loads(str(d["payload"]))
        except json.JSONDecodeError:
            pass
    if d.get("result_json"):
        try:
            d["result"] = json.loads(str(d["result_json"]))
        except json.JSONDecodeError:
            d["result"] = None
    else:
        d["result"] = None
    return d


@dataclass
class QueueWorkerConfig:
    worker_id: str
    poll_interval_s: float = 1.0
    run_once: bool = False


def run_worker_loop(
    *,
    worker_id: str,
    poll_interval_s: float = 1.0,
    run_once: bool = False,
    executor: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    stop_event: threading.Event | None = None,
) -> None:
    """
    Poll SQLite for pending jobs and execute them. Multiple processes may run concurrently;
    claiming uses BEGIN IMMEDIATE for mutual exclusion.
    """
    import time

    from studio_worker.queue_executor import execute_queued_payload

    exec_fn = executor or execute_queued_payload

    while True:
        if stop_event is not None and stop_event.is_set():
            return
        job = claim_next_job(worker_id=worker_id)
        if job is None:
            if run_once:
                return
            if stop_event is not None and stop_event.is_set():
                return
            time.sleep(poll_interval_s)
            continue
        qid = job["id"]
        payload = job["payload"]
        attempts = job["attempts"]
        max_attempts = job["max_attempts"]
        try:
            result = exec_fn(payload)
            mark_completed(
                qid,
                result=result,
                studio_job_id=str(result.get("job_id")),
            )
        except Exception as e:
            mark_failed(qid, error=str(e), attempts=attempts, max_attempts=max_attempts)
        if run_once:
            return
        if stop_event is not None and stop_event.is_set():
            return
        time.sleep(0.05)
