"""
Redis-backed job queue (sorted-set dispatch + per-job hashes).

Requires STUDIO_QUEUE_BACKEND=redis and STUDIO_REDIS_URL (or REDIS_URL).
Uses a short-lived distributed mutex for correctness across API replicas.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, NamedTuple

from studio_worker.scale_config import redis_queue_prefix, redis_url

_client_lock = threading.Lock()
_r: Any = None

try:
    from redis import WatchError
except ImportError:

    class WatchError(Exception):
        """Fallback if redis is not importable (should not happen when queue_redis is used)."""


def _redis():
    global _r
    if _r is not None:
        return _r
    with _client_lock:
        if _r is not None:
            return _r
        try:
            import redis as redis_lib
        except ImportError as e:
            raise RuntimeError(
                "redis package required for STUDIO_QUEUE_BACKEND=redis (pip install 'immersive-studio-worker[redis]')"
            ) from e
        url = redis_url()
        if not url:
            raise RuntimeError("STUDIO_REDIS_URL or REDIS_URL is required for Redis queue backend")
        _r = redis_lib.from_url(url, decode_responses=True)
        return _r


def _prefix() -> str:
    return redis_queue_prefix()


def _k_job(qid: str) -> str:
    return f"{_prefix()}:job:{qid}"


def _k_pending() -> str:
    return f"{_prefix()}:pending"


def _k_timeline() -> str:
    return f"{_prefix()}:timeline"


def _k_all_ids() -> str:
    return f"{_prefix()}:all_ids"


def _k_tenant_set(tenant_id: str | None) -> str:
    tid = "" if tenant_id is None else str(tenant_id)
    return f"{_prefix()}:tenant:{tid}"


def _k_idem(tenant_id: str | None, idem_key: str) -> str:
    tid = "" if tenant_id is None else str(tenant_id)
    return f"{_prefix()}:idem:{tid}:{idem_key}"


def _k_mutex() -> str:
    return f"{_prefix()}:mutex"


@contextmanager
def _write_lock():
    """Distributed mutex (SET NX + WATCH/MULTI release) — works without server Lua."""
    r = _redis()
    token = str(uuid.uuid4())
    while not r.set(_k_mutex(), token, nx=True, ex=120):
        time.sleep(0.01)
    try:
        yield
    finally:
        for _ in range(50):
            pipe = r.pipeline()
            try:
                pipe.watch(_k_mutex())
                cur = pipe.get(_k_mutex())
                if cur != token:
                    pipe.unwatch()
                    return
                pipe.multi()
                pipe.delete(_k_mutex())
                pipe.execute()
                return
            except WatchError:
                continue


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def init_schema() -> None:
    """No-op for Redis (keys are created on demand)."""
    _redis().ping()


class EnqueueOutcome(NamedTuple):
    queue_id: str
    deduplicated: bool


def find_queue_id_by_idempotency(tenant_id: str | None, idempotency_key: str) -> str | None:
    if not idempotency_key.strip():
        return None
    init_schema()
    raw = _redis().get(_k_idem(tenant_id, idempotency_key.strip()))
    return str(raw) if raw else None


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
    score = time.time()
    r = _redis()
    with _write_lock():
        if idem:
            existing = r.get(_k_idem(tid_s, idem))
            if existing:
                return EnqueueOutcome(str(existing), True)
        pipe = r.pipeline(transaction=True)
        pipe.hset(
            _k_job(qid),
            mapping={
                "id": qid,
                "status": "pending",
                "payload": json.dumps(payload),
                "attempts": "0",
                "max_attempts": str(max_attempts),
                "last_error": "",
                "result_json": "",
                "studio_job_id": "",
                "worker_id": "",
                "created_at": now,
                "updated_at": now,
                "tenant_id": tid_s or "",
                "idempotency_key": idem or "",
            },
        )
        pipe.zadd(_k_pending(), {qid: score})
        pipe.zadd(_k_timeline(), {qid: score})
        pipe.sadd(_k_all_ids(), qid)
        if tid_s is not None:
            pipe.sadd(_k_tenant_set(tid_s), qid)
        else:
            pipe.sadd(_k_tenant_set(None), qid)
        pipe.execute()
        if idem:
            r.set(_k_idem(tid_s, idem), qid, ex=60 * 60 * 48)
        _trim_timeline_locked(r)
    return EnqueueOutcome(qid, False)


def _trim_timeline_locked(r: Any) -> None:
    from studio_worker.scale_config import redis_queue_max_timeline

    cap = max(100, redis_queue_max_timeline())
    n = r.zcard(_k_timeline())
    if n > cap:
        r.zremrangebyrank(_k_timeline(), 0, n - cap - 1)


def claim_next_job(*, worker_id: str) -> dict[str, Any] | None:
    init_schema()
    now = _utc_now()
    r = _redis()
    with _write_lock():
        ids = r.zrange(_k_pending(), 0, -1)
        for qid in ids:
            key = _k_job(qid)
            st = r.hget(key, "status")
            if st != "pending":
                r.zrem(_k_pending(), qid)
                continue
            attempts = int(r.hget(key, "attempts") or 0)
            max_a = int(r.hget(key, "max_attempts") or 3)
            if attempts >= max_a:
                continue
            new_att = attempts + 1
            r.hset(
                key,
                mapping={
                    "status": "running",
                    "attempts": str(new_att),
                    "worker_id": worker_id,
                    "updated_at": now,
                },
            )
            r.zrem(_k_pending(), qid)
            payload_raw = r.hget(key, "payload") or "{}"
            payload = json.loads(payload_raw)
            return {
                "id": qid,
                "payload": payload,
                "attempts": new_att,
                "max_attempts": max_a,
            }
    return None


def mark_completed(
    queue_id: str,
    *,
    result: dict[str, Any],
    studio_job_id: str | None,
) -> None:
    now = _utc_now()
    r = _redis()
    with _write_lock():
        r.hset(
            _k_job(queue_id),
            mapping={
                "status": "completed",
                "result_json": json.dumps(result),
                "studio_job_id": studio_job_id or "",
                "last_error": "",
                "updated_at": now,
            },
        )


def mark_failed(queue_id: str, *, error: str, attempts: int, max_attempts: int) -> str:
    now = _utc_now()
    err = error[:4000]
    if attempts >= max_attempts:
        status = "dead"
    else:
        status = "pending"
    r = _redis()
    with _write_lock():
        key = _k_job(queue_id)
        if status == "dead":
            r.hset(
                key,
                mapping={
                    "status": status,
                    "last_error": err,
                    "worker_id": "",
                    "updated_at": now,
                    "idempotency_key": "",
                },
            )
        else:
            r.hset(
                key,
                mapping={
                    "status": status,
                    "last_error": err,
                    "worker_id": "",
                    "updated_at": now,
                },
            )
            r.zadd(_k_pending(), {queue_id: time.time()})
    return status


def _row_from_hash(d: dict[str, str]) -> dict[str, Any]:
    out = dict(d)
    if out.get("payload"):
        try:
            out["payload"] = json.loads(str(out["payload"]))
        except json.JSONDecodeError:
            pass
    rj = out.get("result_json") or ""
    if rj:
        try:
            out["result"] = json.loads(str(rj))
        except json.JSONDecodeError:
            out["result"] = None
    else:
        out["result"] = None
    for empty_key in ("last_error", "studio_job_id", "worker_id", "tenant_id", "idempotency_key"):
        if out.get(empty_key) == "":
            out[empty_key] = None
    return out


def get_queue_job(
    queue_id: str,
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> dict[str, Any] | None:
    init_schema()
    raw = _redis().hgetall(_k_job(queue_id))
    if not raw:
        return None
    d = _row_from_hash(raw)
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
    r = _redis()
    ids = r.zrevrange(_k_timeline(), 0, limit * 4 - 1)
    out: list[dict[str, Any]] = []
    for qid in ids:
        if len(out) >= limit:
            break
        row = get_queue_job(
            str(qid),
            tenant_id=tenant_id,
            include_legacy_unscoped=include_legacy_unscoped,
        )
        if row is not None:
            out.append(row)
    return out


def count_queue_by_status(
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> dict[str, int]:
    init_schema()
    r = _redis()
    counts: dict[str, int] = {}
    if tenant_id is None:
        member_ids = list(r.smembers(_k_all_ids()))
    else:
        acc: set[str] = set(r.smembers(_k_tenant_set(tenant_id)))
        if include_legacy_unscoped:
            acc |= set(r.smembers(_k_tenant_set(None)))
        member_ids = list(acc)
    for qid in member_ids:
        st = r.hget(_k_job(str(qid)), "status")
        if not st:
            continue
        counts[st] = counts.get(st, 0) + 1
    return counts


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
) -> None:
    from studio_worker.queue_executor import execute_queued_payload

    exec_fn = executor or execute_queued_payload

    while True:
        job = claim_next_job(worker_id=worker_id)
        if job is None:
            if run_once:
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
        time.sleep(0.05)
