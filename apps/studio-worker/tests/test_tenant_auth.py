from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


def _assert_queue_slo_matches_between_requests(a: dict[str, Any], b: dict[str, Any]) -> None:
    """Ages are computed per request; two sequential HTTP calls can differ by a few ms."""
    assert set(a.keys()) == set(b.keys())
    assert a["pending_claimable_count"] == b["pending_claimable_count"]
    assert a["running_count"] == b["running_count"]
    for k in ("pending_oldest_age_seconds", "running_oldest_age_seconds"):
        assert (a[k] is None) == (b[k] is None)
        if a[k] is not None:
            assert abs(float(a[k]) - float(b[k])) < 2.0


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


def test_root_returns_api_pointer_json(client_auth_off: TestClient) -> None:
    r = client_auth_off.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body.get("service") == "immersive-studio-worker"
    ep = body.get("endpoints", {})
    assert ep.get("health") == "/api/studio/health"
    assert ep.get("metrics") == "/api/studio/metrics"
    assert ep.get("dashboard") == "/api/studio/dashboard"
    assert body.get("worker_version")


def test_dashboard_and_metrics_send_cache_control_no_store(client_auth_off: TestClient) -> None:
    d = client_auth_off.get("/api/studio/dashboard")
    m = client_auth_off.get("/api/studio/metrics")
    assert "no-store" in (d.headers.get("cache-control") or "").lower()
    assert "no-store" in (m.headers.get("cache-control") or "").lower()


def test_tenant_scoped_get_routes_send_cache_control_no_store(client_auth_off: TestClient) -> None:
    """Operator / billing / job list responses must not be cached by intermediaries."""
    paths = (
        "/api/studio/usage",
        "/api/studio/jobs",
        "/api/studio/queue/jobs",
        "/api/studio/billing/status",
        "/api/studio/paths",
    )
    for path in paths:
        r = client_auth_off.get(path)
        assert r.status_code == 200, path
        assert "no-store" in (r.headers.get("cache-control") or "").lower(), path


def test_favicon_is_no_content(client_auth_off: TestClient) -> None:
    r = client_auth_off.get("/favicon.ico")
    assert r.status_code == 204


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
    assert "slo" in body
    assert isinstance(body["queue"], dict)
    assert isinstance(body["jobs_indexed"], int)
    slo = body["slo"]
    assert "pending_oldest_age_seconds" in slo
    assert "running_oldest_age_seconds" in slo
    assert "pending_claimable_count" in slo
    assert "running_count" in slo


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


def test_dashboard_queue_slo_matches_metrics_with_auth(client_auth_on) -> None:
    c, key, _tid = client_auth_on
    auth = {"Authorization": f"Bearer {key}"}
    d = c.get("/api/studio/dashboard", headers=auth).json()
    m = c.get("/api/studio/metrics", headers=auth).json()
    _assert_queue_slo_matches_between_requests(d["queue_slo"], m["slo"])


def test_dashboard_matches_individual_endpoints_auth_off(client_auth_off: TestClient) -> None:
    d = client_auth_off.get("/api/studio/dashboard").json()
    u = client_auth_off.get("/api/studio/usage").json()
    j = client_auth_off.get("/api/studio/jobs").json()
    b = client_auth_off.get("/api/studio/billing/status").json()
    m = client_auth_off.get("/api/studio/metrics").json()
    assert d["usage"] == u
    assert d["jobs"] == j
    assert d["billing"] == b
    _assert_queue_slo_matches_between_requests(d["queue_slo"], m["slo"])


def test_dashboard_contract_worker_hints(client_auth_off: TestClient) -> None:
    r = client_auth_off.get("/api/studio/dashboard")
    assert r.status_code == 200
    d = r.json()
    wh = d.get("worker_hints")
    assert isinstance(wh, dict)
    assert "ollama_read_timeout_s" in wh
    assert "ollama_read_timeout_max_s" in wh
    assert "ollama_model" in wh
    assert "ollama_base_url" in wh
    assert wh.get("ollama_stream_enabled") is True
    assert isinstance(wh.get("ollama_num_predict"), int)
    assert "ollama_json_format" in wh
    assert "ollama_keep_alive" in wh
    assert isinstance(wh.get("comfy_image_wait_s"), (int, float))
    assert isinstance(wh.get("comfy_max_concurrent"), int)
    assert "embedded_queue_worker" in wh
    assert "queue_backend" in wh
    assert "job_textures_before_mesh" in wh
    qs = d.get("queue_slo")
    assert isinstance(qs, dict)
    assert set(qs.keys()) >= {
        "pending_oldest_age_seconds",
        "running_oldest_age_seconds",
        "pending_claimable_count",
        "running_count",
    }


def test_dashboard_401_without_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STUDIO_API_AUTH_REQUIRED", "1")
    monkeypatch.setattr(
        "studio_worker.paths.tenants_db_path", lambda: tmp_path / "t-dash.sqlite"
    )
    from studio_worker.api import app

    with TestClient(app) as c:
        r = c.get("/api/studio/dashboard")
        assert r.status_code == 401
