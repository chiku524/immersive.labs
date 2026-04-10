"""Redis queue backend (fakeredis; does not require a live Redis server)."""

from __future__ import annotations

import pytest

fakeredis = pytest.importorskip("fakeredis")

import studio_worker.queue_redis as qr


@pytest.fixture
def rq(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(qr, "_r", fake)
    fake.flushall()
    yield fake


def test_enqueue_claim_complete(rq) -> None:
    qid = qr.enqueue_job(
        {"user_prompt": "x", "mock": True, "generate_textures": False},
        max_attempts=2,
    ).queue_id
    job = qr.claim_next_job(worker_id="w1")
    assert job is not None
    assert job["id"] == qid
    assert job["attempts"] == 1
    qr.mark_completed(
        qid,
        result={"job_id": "j1", "ok": True},
        studio_job_id="j1",
    )
    row = qr.get_queue_job(qid)
    assert row is not None
    assert row["status"] == "completed"
    assert row["studio_job_id"] == "j1"
    assert row["result"]["job_id"] == "j1"


def test_retry_then_dead(rq) -> None:
    qid = qr.enqueue_job({"user_prompt": "x", "mock": True}, max_attempts=2).queue_id
    j1 = qr.claim_next_job(worker_id="w1")
    assert j1 is not None
    s1 = qr.mark_failed(qid, error="e1", attempts=j1["attempts"], max_attempts=j1["max_attempts"])
    assert s1 == "pending"
    j2 = qr.claim_next_job(worker_id="w1")
    assert j2 is not None
    assert j2["attempts"] == 2
    s2 = qr.mark_failed(qid, error="e2", attempts=j2["attempts"], max_attempts=j2["max_attempts"])
    assert s2 == "dead"
    row = qr.get_queue_job(qid)
    assert row is not None
    assert row["status"] == "dead"


def test_idempotency(rq) -> None:
    tid = "tenant-a"
    a = qr.enqueue_job(
        {"user_prompt": "x", "mock": True},
        tenant_id=tid,
        idempotency_key="idem-1",
    )
    b = qr.enqueue_job(
        {"user_prompt": "x", "mock": True},
        tenant_id=tid,
        idempotency_key="idem-1",
    )
    assert a.queue_id == b.queue_id
    assert a.deduplicated is False
    assert b.deduplicated is True


def test_count_queue_by_status(rq) -> None:
    qr.enqueue_job({"user_prompt": "a", "mock": True})
    qr.enqueue_job({"user_prompt": "b", "mock": True})
    c = qr.count_queue_by_status()
    assert c.get("pending", 0) >= 2
