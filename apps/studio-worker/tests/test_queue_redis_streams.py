"""Redis Streams queue (fakeredis)."""

from __future__ import annotations

import pytest

fakeredis = pytest.importorskip("fakeredis")

import studio_worker.queue_redis as zq
import studio_worker.queue_redis_streams as qs


@pytest.fixture
def rs(monkeypatch):
    monkeypatch.setenv("STUDIO_REDIS_STREAM_BLOCK_MS", "50")
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(zq, "_r", fake)
    qs._group_ready = False
    fake.flushall()
    yield fake
    qs._group_ready = False


def test_streams_enqueue_claim_complete(rs) -> None:
    qid = qs.enqueue_job(
        {"user_prompt": "x", "mock": True, "generate_textures": False},
        max_attempts=2,
    ).queue_id
    job = qs.claim_next_job(worker_id="w1")
    assert job is not None
    assert job["id"] == qid
    assert job["attempts"] == 1
    qs.mark_completed(
        qid,
        result={"job_id": "j1", "ok": True},
        studio_job_id="j1",
    )
    row = qs.get_queue_job(qid)
    assert row is not None
    assert row["status"] == "completed"
    assert row["studio_job_id"] == "j1"
    assert row["result"]["job_id"] == "j1"


def test_streams_retry_then_dead(rs) -> None:
    qid = qs.enqueue_job({"user_prompt": "x", "mock": True}, max_attempts=2).queue_id
    j1 = qs.claim_next_job(worker_id="w1")
    assert j1 is not None
    s1 = qs.mark_failed(qid, error="e1", attempts=j1["attempts"], max_attempts=j1["max_attempts"])
    assert s1 == "pending"
    j2 = qs.claim_next_job(worker_id="w1")
    assert j2 is not None
    assert j2["attempts"] == 2
    s2 = qs.mark_failed(qid, error="e2", attempts=j2["attempts"], max_attempts=j2["max_attempts"])
    assert s2 == "dead"
    row = qs.get_queue_job(qid)
    assert row is not None
    assert row["status"] == "dead"


def test_streams_idempotency(rs) -> None:
    tid = "tenant-a"
    a = qs.enqueue_job(
        {"user_prompt": "x", "mock": True},
        tenant_id=tid,
        idempotency_key="idem-1",
    )
    b = qs.enqueue_job(
        {"user_prompt": "x", "mock": True},
        tenant_id=tid,
        idempotency_key="idem-1",
    )
    assert a.queue_id == b.queue_id
    assert a.deduplicated is False
    assert b.deduplicated is True


def test_streams_stale_stream_entry_is_acked(rs) -> None:
    """If hash is not pending, stream entry is ACKed and claim continues."""
    qid = qs.enqueue_job({"user_prompt": "z", "mock": True}).queue_id
    qs.mark_completed(qid, result={"job_id": "x"}, studio_job_id="x")
    qs.enqueue_job({"user_prompt": "next", "mock": True})
    job = qs.claim_next_job(worker_id="w2")
    assert job is not None
    assert job["payload"]["user_prompt"] == "next"
