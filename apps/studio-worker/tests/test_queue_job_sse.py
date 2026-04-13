from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_auth_with_queue_sse(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_API_AUTH_REQUIRED", "1")
    monkeypatch.setenv("STUDIO_EMBEDDED_QUEUE_WORKER", "1")
    monkeypatch.setattr(
        "studio_worker.paths.tenants_db_path",
        lambda: tmp_path / "tenants.sqlite",
    )
    monkeypatch.setattr(
        "studio_worker.paths.queue_db_path",
        lambda: tmp_path / "queue.sqlite",
    )
    from studio_worker import tenants_db
    from studio_worker.api import app

    tenants_db.init_tenants_schema()
    tid = tenants_db.create_tenant(name="SseTest", tier_id="indie")
    key = tenants_db.create_api_key(tenant_id=tid, label="pytest-sse")

    with TestClient(app) as c:
        yield c, key


def test_queue_job_sse_emits_completed(client_auth_with_queue_sse) -> None:
    c, key = client_auth_with_queue_sse
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    r = c.post(
        "/api/studio/queue/jobs",
        json={"prompt": "sse probe", "mock": True, "max_attempts": 1},
        headers=h,
    )
    assert r.status_code == 200
    qid = r.json()["queue_id"]

    buf = b""
    deadline = time.time() + 45
    with c.stream(
        "GET",
        f"/api/studio/queue/jobs/{qid}/events",
        headers={"Authorization": f"Bearer {key}", "Accept": "text/event-stream"},
    ) as sr:
        assert sr.status_code == 200
        assert "text/event-stream" in (sr.headers.get("content-type") or "").lower()
        for chunk in sr.iter_bytes():
            buf += chunk
            if b'"status":"completed"' in buf:
                break
            if time.time() > deadline:
                pytest.fail(f"SSE timed out; buf={buf[:500]!r}")


def test_queue_job_sse_unknown_queue_event(client_auth_with_queue_sse) -> None:
    c, key = client_auth_with_queue_sse
    buf = b""
    with c.stream(
        "GET",
        "/api/studio/queue/jobs/00000000-0000-0000-0000-000000000001/events",
        headers={"Authorization": f"Bearer {key}", "Accept": "text/event-stream"},
    ) as sr:
        assert sr.status_code == 200
        for chunk in sr.iter_bytes():
            buf += chunk
            if b"event: error" in buf:
                break
    assert b"Unknown queue_id" in buf
