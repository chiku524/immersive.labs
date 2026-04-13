"""
Postgres-backed job queue (shared across API replicas).

Requires DATABASE_URL and STUDIO_QUEUE_BACKEND=postgres.
Schema mirrors sqlite queue_jobs for operational parity.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, NamedTuple

import psycopg
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

from studio_worker.scale_config import database_url

_lock = threading.RLock()


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _connect() -> psycopg.Connection:
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is required for Postgres queue backend")
    return psycopg.connect(url, autocommit=False)


def init_schema() -> None:
    with _lock:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
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
                      updated_at TEXT NOT NULL,
                      tenant_id TEXT,
                      idempotency_key TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_queue_status_created
                      ON queue_jobs (status, created_at);
                    CREATE INDEX IF NOT EXISTS idx_queue_tenant_created
                      ON queue_jobs (tenant_id, created_at);
                    DROP INDEX IF EXISTS idx_queue_idempotency;
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_idempotency
                      ON queue_jobs (coalesce(tenant_id, ''), idempotency_key)
                      WHERE idempotency_key IS NOT NULL AND trim(idempotency_key) <> '';
                    """
                )
            conn.commit()


class EnqueueOutcome(NamedTuple):
    queue_id: str
    deduplicated: bool


def count_queue_by_status(
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> dict[str, int]:
    init_schema()
    counts: dict[str, int] = {}
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if tenant_id is None:
                    cur.execute(
                        "SELECT status, COUNT(*) AS c FROM queue_jobs GROUP BY status"
                    )
                elif include_legacy_unscoped:
                    cur.execute(
                        """
                        SELECT status, COUNT(*) AS c FROM queue_jobs
                        WHERE tenant_id = %s OR tenant_id IS NULL
                        GROUP BY status
                        """,
                        (tenant_id,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT status, COUNT(*) AS c FROM queue_jobs
                        WHERE tenant_id = %s
                        GROUP BY status
                        """,
                        (tenant_id,),
                    )
                for r in cur.fetchall():
                    counts[str(r["status"])] = int(r["c"])
            conn.commit()
    return counts


def find_queue_id_by_idempotency(tenant_id: str | None, idempotency_key: str) -> str | None:
    if not idempotency_key.strip():
        return None
    init_schema()
    tid_coalesce = "" if tenant_id is None else str(tenant_id)
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id FROM queue_jobs
                    WHERE coalesce(tenant_id, '') = %s AND idempotency_key = %s
                    LIMIT 1
                    """,
                    (tid_coalesce, idempotency_key.strip()),
                )
                row = cur.fetchone()
            conn.commit()
    return str(row["id"]) if row else None


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
    with _lock:
        with _connect() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO queue_jobs (
                          id, status, payload, attempts, max_attempts,
                          last_error, result_json, studio_job_id, worker_id, created_at, updated_at,
                          tenant_id, idempotency_key
                        ) VALUES (%s, 'pending', %s, 0, %s, NULL, NULL, NULL, NULL, %s, %s, %s, %s)
                        """,
                        (
                            qid,
                            json.dumps(payload),
                            max_attempts,
                            now,
                            now,
                            tid_s,
                            idem,
                        ),
                    )
                conn.commit()
            except pg_errors.UniqueViolation:
                conn.rollback()
                existing = find_queue_id_by_idempotency(tid_s, idem or "")
                if existing:
                    return EnqueueOutcome(existing, True)
                raise
    return EnqueueOutcome(qid, False)


def claim_next_job(*, worker_id: str) -> dict[str, Any] | None:
    init_schema()
    now = _utc_now()
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    WITH picked AS (
                      SELECT id FROM queue_jobs
                      WHERE status = 'pending' AND attempts < max_attempts
                      ORDER BY created_at ASC
                      LIMIT 1
                      FOR UPDATE SKIP LOCKED
                    )
                    UPDATE queue_jobs q
                    SET status = 'running',
                        attempts = q.attempts + 1,
                        worker_id = %s,
                        updated_at = %s
                    FROM picked
                    WHERE q.id = picked.id
                    RETURNING q.id, q.payload, q.attempts, q.max_attempts
                    """,
                    (worker_id, now),
                )
                row = cur.fetchone()
            conn.commit()
    if row is None:
        return None
    payload = json.loads(str(row["payload"]))
    return {
        "id": str(row["id"]),
        "payload": payload,
        "attempts": int(row["attempts"]),
        "max_attempts": int(row["max_attempts"]),
    }


def claim_job_by_id(queue_id: str, *, worker_id: str) -> dict[str, Any] | None:
    """
    Claim a specific pending row (used when an external broker, e.g. SQS, delivers the id).
    Returns the same shape as claim_next_job or None if not claimable.
    """
    init_schema()
    now = _utc_now()
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE queue_jobs
                    SET status = 'running',
                        attempts = attempts + 1,
                        worker_id = %s,
                        updated_at = %s
                    WHERE id = %s AND status = 'pending' AND attempts < max_attempts
                    RETURNING id, payload, attempts, max_attempts
                    """,
                    (worker_id, now, queue_id),
                )
                row = cur.fetchone()
            conn.commit()
    if row is None:
        return None
    payload = json.loads(str(row["payload"]))
    return {
        "id": str(row["id"]),
        "payload": payload,
        "attempts": int(row["attempts"]),
        "max_attempts": int(row["max_attempts"]),
    }


def mark_completed(
    queue_id: str,
    *,
    result: dict[str, Any],
    studio_job_id: str | None,
) -> None:
    now = _utc_now()
    with _lock:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE queue_jobs
                    SET status = 'completed',
                        result_json = %s,
                        studio_job_id = %s,
                        last_error = NULL,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (json.dumps(result), studio_job_id, now, queue_id),
                )
            conn.commit()


def mark_failed(queue_id: str, *, error: str, attempts: int, max_attempts: int) -> str:
    now = _utc_now()
    err = error[:4000]
    if attempts >= max_attempts:
        status = "dead"
    else:
        status = "pending"
    with _lock:
        with _connect() as conn:
            with conn.cursor() as cur:
                if status == "dead":
                    cur.execute(
                        """
                        UPDATE queue_jobs
                        SET status = %s,
                            last_error = %s,
                            worker_id = NULL,
                            updated_at = %s,
                            idempotency_key = NULL
                        WHERE id = %s
                        """,
                        (status, err, now, queue_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE queue_jobs
                        SET status = %s,
                            last_error = %s,
                            worker_id = NULL,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        (status, err, now, queue_id),
                    )
            conn.commit()
    return status


def get_queue_job(
    queue_id: str,
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> dict[str, Any] | None:
    init_schema()
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM queue_jobs WHERE id = %s", (queue_id,))
                row = cur.fetchone()
            conn.commit()
    if row is None:
        return None
    d = _row_to_dict(row)
    if tenant_id is not None:
        row_tid = d.get("tenant_id")
        if row_tid != tenant_id and not (include_legacy_unscoped and row_tid is None):
            return None
    return d


def list_queue_jobs(
    *,
    limit: int = 50,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> list[dict[str, Any]]:
    init_schema()
    limit = max(1, min(limit, 500))
    with _lock:
        with _connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if tenant_id is None:
                    cur.execute(
                        """
                        SELECT * FROM queue_jobs
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                elif include_legacy_unscoped:
                    cur.execute(
                        """
                        SELECT * FROM queue_jobs
                        WHERE tenant_id = %s OR tenant_id IS NULL
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (tenant_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT * FROM queue_jobs
                        WHERE tenant_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (tenant_id, limit),
                    )
                rows = cur.fetchall()
            conn.commit()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
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
