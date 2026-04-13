"""
SQS as dispatch broker with Postgres as source of truth for queue rows (list/get/metrics/idempotency).

Requires STUDIO_QUEUE_BACKEND=sqs, STUDIO_SQS_QUEUE_URL, DATABASE_URL, and pip extra for psycopg + boto3.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

from studio_worker import queue_postgres as qp
from studio_worker.scale_config import (
    aws_region,
    sqs_endpoint_url,
    sqs_queue_url,
    sqs_visibility_timeout,
    sqs_wait_seconds,
)

try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore[misc, assignment]

_tls = threading.local()

EnqueueOutcome = qp.EnqueueOutcome
QueueWorkerConfig = qp.QueueWorkerConfig


def _sqs_client():
    if boto3 is None:
        raise RuntimeError(
            "boto3 is required for STUDIO_QUEUE_BACKEND=sqs (pip install 'immersive-studio[s3]' or scale)"
        )
    kwargs: dict[str, Any] = {"region_name": aws_region()}
    ep = sqs_endpoint_url()
    if ep:
        kwargs["endpoint_url"] = ep
    return boto3.client("sqs", **kwargs)  # type: ignore[union-attr]


def init_schema() -> None:
    qp.init_schema()


def find_queue_id_by_idempotency(tenant_id: str | None, idempotency_key: str) -> str | None:
    return qp.find_queue_id_by_idempotency(tenant_id, idempotency_key)


def enqueue_job(
    payload: dict[str, Any],
    *,
    max_attempts: int = 3,
    queue_id: str | None = None,
    tenant_id: str | None = None,
    idempotency_key: str | None = None,
) -> qp.EnqueueOutcome:
    out = qp.enqueue_job(
        payload,
        max_attempts=max_attempts,
        queue_id=queue_id,
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
    )
    if not out.deduplicated:
        url = sqs_queue_url()
        if not url:
            raise RuntimeError("STUDIO_SQS_QUEUE_URL is not set")
        body = json.dumps({"v": 1, "queue_id": out.queue_id})
        _sqs_client().send_message(QueueUrl=url, MessageBody=body)
    return out


def _remember_sqs_claim(queue_id: str, receipt_handle: str, queue_url: str) -> None:
    _tls.sqs_claim = (queue_id, receipt_handle, queue_url)


def _clear_sqs_claim(queue_id: str) -> None:
    c = getattr(_tls, "sqs_claim", None)
    if c and c[0] == queue_id:
        try:
            _sqs_client().delete_message(QueueUrl=c[2], ReceiptHandle=c[1])
        finally:
            delattr(_tls, "sqs_claim")


def claim_next_job(*, worker_id: str) -> dict[str, Any] | None:
    url = sqs_queue_url()
    if not url:
        raise RuntimeError("STUDIO_SQS_QUEUE_URL is not set")
    client = _sqs_client()
    wait = sqs_wait_seconds()
    vis = sqs_visibility_timeout()
    while True:
        resp = client.receive_message(
            QueueUrl=url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=wait,
            VisibilityTimeout=vis,
        )
        messages = resp.get("Messages") or []
        if not messages:
            return None
        m = messages[0]
        receipt = m["ReceiptHandle"]
        try:
            body = json.loads(m["Body"])
        except json.JSONDecodeError:
            client.delete_message(QueueUrl=url, ReceiptHandle=receipt)
            continue
        qid = str(body.get("queue_id") or "").strip()
        if not qid:
            client.delete_message(QueueUrl=url, ReceiptHandle=receipt)
            continue
        job = qp.claim_job_by_id(qid, worker_id=worker_id)
        if job is None:
            client.delete_message(QueueUrl=url, ReceiptHandle=receipt)
            continue
        _remember_sqs_claim(job["id"], receipt, url)
        return job


def mark_completed(
    queue_id: str,
    *,
    result: dict[str, Any],
    studio_job_id: str | None,
) -> None:
    qp.mark_completed(queue_id, result=result, studio_job_id=studio_job_id)
    _clear_sqs_claim(queue_id)


def mark_failed(queue_id: str, *, error: str, attempts: int, max_attempts: int) -> str:
    status = qp.mark_failed(queue_id, error=error, attempts=attempts, max_attempts=max_attempts)
    _clear_sqs_claim(queue_id)
    if status == "pending":
        url = sqs_queue_url()
        if url:
            body = json.dumps({"v": 1, "queue_id": queue_id})
            _sqs_client().send_message(QueueUrl=url, MessageBody=body)
    return status


def get_queue_job(
    queue_id: str,
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> dict[str, Any] | None:
    return qp.get_queue_job(
        queue_id,
        tenant_id=tenant_id,
        include_legacy_unscoped=include_legacy_unscoped,
    )


def list_queue_jobs(
    *,
    limit: int = 50,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> list[dict[str, Any]]:
    return qp.list_queue_jobs(
        limit=limit,
        tenant_id=tenant_id,
        include_legacy_unscoped=include_legacy_unscoped,
    )


def count_queue_by_status(
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> dict[str, int]:
    return qp.count_queue_by_status(
        tenant_id=tenant_id,
        include_legacy_unscoped=include_legacy_unscoped,
    )


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
