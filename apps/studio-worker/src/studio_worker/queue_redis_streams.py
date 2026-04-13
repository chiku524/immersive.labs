"""
Redis Streams dispatch (XADD + XREADGROUP / XACK) with hashes for job rows (same API as queue_redis).

Requires STUDIO_QUEUE_BACKEND=redis, STUDIO_REDIS_QUEUE_ENGINE=streams, and STUDIO_REDIS_URL / REDIS_URL.

Keys live under `redis_queue_streams_prefix()` so they do not collide with `queue_redis` (zset) keys.
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

from studio_worker.queue_redis import _redis
from studio_worker.scale_config import (
    redis_queue_max_timeline,
    redis_queue_streams_prefix,
    redis_stream_group,
    redis_streams_maxlen,
    redis_streams_read_block_ms,
)

try:
    from redis import WatchError
except ImportError:

    class WatchError(Exception):
        """Fallback if redis is not importable."""


_tls = threading.local()
_group_ready = False
_group_ready_lock = threading.Lock()


def _prefix() -> str:
    return redis_queue_streams_prefix()


def _k_job(qid: str) -> str:
    return f"{_prefix()}:job:{qid}"


def _k_stream() -> str:
    return f"{_prefix()}:dispatch"


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


def _stream_group() -> str:
    return redis_stream_group()


def _ensure_consumer_group() -> None:
    global _group_ready
    if _group_ready:
        return
    with _group_ready_lock:
        if _group_ready:
            return
        r = _redis()
        stream = _k_stream()
        group = _stream_group()
        try:
            r.xgroup_create(stream, group, id="0", mkstream=True)
        except Exception as e:
            if "BUSYGROUP" not in str(e).upper():
                raise
        _group_ready = True


def init_schema() -> None:
    _redis().ping()
    _ensure_consumer_group()


class EnqueueOutcome(NamedTuple):
    queue_id: str
    deduplicated: bool


def _remember_stream_ack(queue_id: str, stream: str, group: str, msg_id: str) -> None:
    _tls.stream_ack = (queue_id, stream, group, msg_id)


def _clear_stream_ack(queue_id: str) -> None:
    t = getattr(_tls, "stream_ack", None)
    if not t or t[0] != queue_id:
        return
    _, stream, group, msg_id = t
    r = _redis()
    r.xack(stream, group, msg_id)
    delattr(_tls, "stream_ack")


def _sanitize_consumer(worker_id: str) -> str:
    out = "".join(c if c.isalnum() or c in "._-:" else "_" for c in worker_id)
    return (out or "worker")[:80]


def find_queue_id_by_idempotency(tenant_id: str | None, idempotency_key: str) -> str | None:
    if not idempotency_key.strip():
        return None
    init_schema()
    raw = _redis().get(_k_idem(tenant_id, idempotency_key.strip()))
    return str(raw) if raw else None


def _trim_timeline_locked(r: Any) -> None:
    cap = max(100, redis_queue_max_timeline())
    n = r.zcard(_k_timeline())
    if n > cap:
        r.zremrangebyrank(_k_timeline(), 0, n - cap - 1)


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
    stream = _k_stream()
    maxlen = redis_streams_maxlen()
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
        pipe.zadd(_k_timeline(), {qid: score})
        pipe.sadd(_k_all_ids(), qid)
        if tid_s is not None:
            pipe.sadd(_k_tenant_set(tid_s), qid)
        else:
            pipe.sadd(_k_tenant_set(None), qid)
        pipe.execute()
        r.xadd(
            stream,
            {"queue_id": qid},
            maxlen=maxlen,
            approximate=True,
        )
        if idem:
            r.set(_k_idem(tid_s, idem), qid, ex=60 * 60 * 48)
        _trim_timeline_locked(r)
    return EnqueueOutcome(qid, False)


def claim_next_job(*, worker_id: str) -> dict[str, Any] | None:
    init_schema()
    r = _redis()
    stream = _k_stream()
    group = _stream_group()
    consumer = _sanitize_consumer(worker_id)
    block_ms = redis_streams_read_block_ms()
    now = _utc_now()

    while True:
        resp = r.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=1,
            block=block_ms,
        )
        if not resp:
            return None
        _sname, messages = resp[0]
        if not messages:
            return None
        msg_id, fields = messages[0]
        qid = str(fields.get("queue_id") or "").strip()
        if not qid:
            r.xack(stream, group, msg_id)
            continue

        with _write_lock():
            key = _k_job(qid)
            st = r.hget(key, "status")
            if st != "pending":
                r.xack(stream, group, msg_id)
                continue
            attempts = int(r.hget(key, "attempts") or 0)
            max_a = int(r.hget(key, "max_attempts") or 3)
            if attempts >= max_a:
                r.xack(stream, group, msg_id)
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
            payload_raw = r.hget(key, "payload") or "{}"
            payload = json.loads(payload_raw)

        _remember_stream_ack(qid, stream, group, msg_id)
        return {
            "id": qid,
            "payload": payload,
            "attempts": new_att,
            "max_attempts": max_a,
        }


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
    _clear_stream_ack(queue_id)


def mark_failed(queue_id: str, *, error: str, attempts: int, max_attempts: int) -> str:
    now = _utc_now()
    err = error[:4000]
    if attempts >= max_attempts:
        status = "dead"
    else:
        status = "pending"
    r = _redis()
    stream = _k_stream()
    maxlen = redis_streams_maxlen()
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
    _clear_stream_ack(queue_id)
    if status == "pending":
        r.xadd(stream, {"queue_id": queue_id}, maxlen=maxlen, approximate=True)
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
    stop_event: threading.Event | None = None,
) -> None:
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
