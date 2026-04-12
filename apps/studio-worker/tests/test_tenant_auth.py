from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_auth_off(monkeypatch):
    monkeypatch.delenv("STUDIO_API_AUTH_REQUIRED", raising=False)
    from studio_worker.api import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_auth_on(monkeypatch, tmp_path):
    monkeypatch.setenv("STUDIO_API_AUTH_REQUIRED", "1")
    monkeypatch.setattr(
        "studio_worker.paths.tenants_db_path", lambda: tmp_path / "tenants.sqlite"
    )
    from studio_worker import tenants_db
    from studio_worker.api import app

    tenants_db.init_tenants_schema()
    tid = tenants_db.create_tenant(name="Test", tier_id="indie")
    key = tenants_db.create_api_key(tenant_id=tid, label="pytest")

    with TestClient(app) as c:
        yield c, key, tid


def test_health_shows_auth_flag(client_auth_off: TestClient) -> None:
    r = client_auth_off.get("/api/studio/health")
    assert r.status_code == 200
    body = r.json()
    assert body["auth_required"] is False
    assert body["stripe_webhook_configured"] is False
    assert body.get("worker_version")


def test_health_auth_required_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_API_AUTH_REQUIRED", "1")
    from studio_worker.api import app

    with TestClient(app) as c:
        r = c.get("/api/studio/health")
        assert r.status_code == 200
        body = r.json()
        assert body["auth_required"] is True
        assert body["stripe_webhook_configured"] is False


def test_health_stripe_webhook_flag_when_secret_set(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_dummy")
    from studio_worker.api import app

    with TestClient(app) as c:
        r = c.get("/api/studio/health")
        assert r.status_code == 200
        assert r.json()["stripe_webhook_configured"] is True


def test_usage_ok_when_auth_disabled(client_auth_off: TestClient) -> None:
    r = client_auth_off.get("/api/studio/usage")
    assert r.status_code == 200
    body = r.json()
    assert body["limits_enforced"] is False


def test_metrics_ok_when_auth_disabled(client_auth_off: TestClient) -> None:
    r = client_auth_off.get("/api/studio/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "queue" in body
    assert "jobs_indexed" in body
    assert isinstance(body["queue"], dict)
    assert isinstance(body["jobs_indexed"], int)


def test_protected_route_401_without_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STUDIO_API_AUTH_REQUIRED", "1")
    monkeypatch.setattr(
        "studio_worker.paths.tenants_db_path", lambda: tmp_path / "t2.sqlite"
    )
    from studio_worker.api import app

    with TestClient(app) as c:
        r = c.get("/api/studio/usage")
        assert r.status_code == 401


def test_usage_with_valid_key(client_auth_on) -> None:
    c, key, _tid = client_auth_on
    r = c.get("/api/studio/usage", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200
    body = r.json()
    assert body["limits_enforced"] is True
    assert body["tier_id"] == "indie"
    assert body["credits_cap"] == 600
