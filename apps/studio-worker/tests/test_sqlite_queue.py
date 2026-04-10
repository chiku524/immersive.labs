from __future__ import annotations

import pytest

from studio_worker.sqlite_queue import (
    claim_next_job,
    enqueue_job,
    get_queue_job,
    list_queue_jobs,
    mark_completed,
    mark_failed,
)


@pytest.fixture
def isolated_queue_db(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "studio_worker.queue_sqlite.queue_db_path", lambda: tmp_path / "queue.sqlite"
    )


def test_enqueue_claim_complete(isolated_queue_db) -> None:
    qid = enqueue_job(
        {"user_prompt": "x", "mock": True, "generate_textures": False},
        max_attempts=2,
    ).queue_id
    job = claim_next_job(worker_id="w1")
    assert job is not None
    assert job["id"] == qid
    assert job["attempts"] == 1
    mark_completed(
        qid,
        result={"job_id": "j1", "ok": True},
        studio_job_id="j1",
    )
    row = get_queue_job(qid)
    assert row is not None
    assert row["status"] == "completed"
    assert row["studio_job_id"] == "j1"
    assert row["result"]["job_id"] == "j1"


def test_retry_then_dead(isolated_queue_db) -> None:
    qid = enqueue_job({"user_prompt": "x", "mock": True}, max_attempts=2).queue_id
    j1 = claim_next_job(worker_id="w1")
    assert j1 is not None
    s1 = mark_failed(qid, error="e1", attempts=j1["attempts"], max_attempts=j1["max_attempts"])
    assert s1 == "pending"
    j2 = claim_next_job(worker_id="w1")
    assert j2 is not None
    assert j2["attempts"] == 2
    s2 = mark_failed(qid, error="e2", attempts=j2["attempts"], max_attempts=j2["max_attempts"])
    assert s2 == "dead"
    row = get_queue_job(qid)
    assert row is not None
    assert row["status"] == "dead"


def test_list_queue_jobs(isolated_queue_db) -> None:
    enqueue_job({"user_prompt": "a", "mock": True})
    enqueue_job({"user_prompt": "b", "mock": True})


def test_idempotency_same_queue_id(isolated_queue_db) -> None:
    tid = "tenant-a"
    a = enqueue_job(
        {"user_prompt": "x", "mock": True},
        tenant_id=tid,
        idempotency_key="idem-1",
    )
    b = enqueue_job(
        {"user_prompt": "x", "mock": True},
        tenant_id=tid,
        idempotency_key="idem-1",
    )
    assert a.queue_id == b.queue_id
    assert a.deduplicated is False
    assert b.deduplicated is True


def test_dead_job_releases_idempotency_key(isolated_queue_db) -> None:
    tid = "tenant-b"
    qid = enqueue_job(
        {"user_prompt": "x", "mock": True},
        tenant_id=tid,
        idempotency_key="idem-2",
        max_attempts=1,
    ).queue_id
    j = claim_next_job(worker_id="w")
    assert j is not None
    mark_failed(qid, error="fail", attempts=j["attempts"], max_attempts=j["max_attempts"])
    row = get_queue_job(qid)
    assert row["status"] == "dead"
    c = enqueue_job(
        {"user_prompt": "retry", "mock": True},
        tenant_id=tid,
        idempotency_key="idem-2",
    )
    assert c.deduplicated is False
    assert c.queue_id != qid
    rows = list_queue_jobs(limit=10)
    assert len(rows) >= 2
