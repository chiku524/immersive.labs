from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_auth_with_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_API_AUTH_REQUIRED", "1")
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
    tid = tenants_db.create_tenant(name="QueueTest", tier_id="indie")
    key = tenants_db.create_api_key(tenant_id=tid, label="pytest-queue")

    with TestClient(app) as c:
        yield c, key


def test_enqueue_idempotency_returns_same_queue_id(client_auth_with_queue) -> None:
    c, key = client_auth_with_queue
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {
        "prompt": "wooden crate",
        "mock": True,
        "generate_textures": False,
        "idempotency_key": "client-submit-abc",
    }
    r1 = c.post("/api/studio/queue/jobs", json=body, headers=h)
    assert r1.status_code == 200
    j1 = r1.json()
    assert j1["deduplicated"] is False
    q1 = j1["queue_id"]

    r2 = c.post("/api/studio/queue/jobs", json=body, headers=h)
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["deduplicated"] is True
    assert j2["queue_id"] == q1


def test_enqueue_without_idempotency_gets_distinct_ids(client_auth_with_queue) -> None:
    c, key = client_auth_with_queue
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"prompt": "barrel", "mock": True, "generate_textures": False}
    r1 = c.post("/api/studio/queue/jobs", json=body, headers=h)
    r2 = c.post("/api/studio/queue/jobs", json=body, headers=h)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["queue_id"] != r2.json()["queue_id"]
