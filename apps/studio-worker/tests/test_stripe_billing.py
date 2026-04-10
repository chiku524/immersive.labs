from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from studio_worker import tenants_db
from studio_worker.stripe_billing import (
    apply_subscription_to_tenant,
    handle_checkout_session_async_payment_failed,
    handle_checkout_session_completed,
    handle_stripe_event,
    handle_subscription_deleted,
    handle_subscription_trial_will_end,
    handle_subscription_updated,
    tier_from_subscription_object,
)


@pytest.fixture
def tenant_db(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "studio_worker.paths.tenants_db_path", lambda: tmp_path / "tenants.sqlite"
    )
    tenants_db.init_tenants_schema()
    tid = tenants_db.create_tenant(name="Studio", tier_id="free")
    return tid


def test_tier_from_subscription_uses_price_map(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_STRIPE_PRICE_INDIE", "price_abc123")
    sub = {"items": {"data": [{"price": {"id": "price_abc123", "metadata": {}}}]}}
    assert tier_from_subscription_object(sub) == "indie"


def test_tier_from_subscription_metadata_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_STRIPE_PRICE_INDIE", "price_abc123")
    sub = {
        "items": {
            "data": [{"price": {"id": "price_other", "metadata": {"tier": "team"}}}],
        }
    }
    assert tier_from_subscription_object(sub) == "team"


def test_checkout_session_completed_links_and_calls_apply(tenant_db: str) -> None:
    tid = tenant_db
    session = {
        "mode": "subscription",
        "metadata": {"tenant_id": tid},
        "client_reference_id": tid,
        "customer": "cus_test123",
        "subscription": "sub_test456",
    }
    with patch("studio_worker.stripe_billing.apply_subscription_to_tenant") as m_apply:
        handle_checkout_session_completed(session)
        m_apply.assert_called_once_with(tid, "sub_test456")
    row = tenants_db.get_tenant(tid)
    assert row is not None
    assert row["stripe_customer_id"] == "cus_test123"
    assert row["stripe_subscription_id"] == "sub_test456"


def test_subscription_updated_sets_tier(tenant_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_STRIPE_PRICE_TEAM", "price_team_x")
    tid = tenant_db
    tenants_db.link_stripe_customer(tid, "cus_z")
    sub = {
        "id": "sub_z",
        "customer": "cus_z",
        "status": "active",
        "items": {"data": [{"price": {"id": "price_team_x", "metadata": {}}}]},
    }
    handle_subscription_updated(sub)
    row = tenants_db.get_tenant(tid)
    assert row is not None
    assert row["tier_id"] == "team"


def test_apply_subscription_incomplete_keeps_free_tier(
    tenant_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STUDIO_STRIPE_PRICE_INDIE", "price_x")
    tid = tenant_db
    tenants_db.link_stripe_customer(tid, "cus_inc")

    fake_sub = {
        "id": "sub_inc",
        "status": "incomplete",
        "items": {"data": [{"price": {"id": "price_x", "metadata": {}}}]},
    }

    class FakeStripe:
        class Subscription:
            @staticmethod
            def retrieve(sid, expand=None):
                assert sid == "sub_inc"
                return fake_sub

    monkeypatch.setitem(__import__("sys").modules, "stripe", FakeStripe)
    monkeypatch.setattr("studio_worker.stripe_billing.configure_stripe", lambda: None)
    monkeypatch.setattr("studio_worker.stripe_billing.stripe_secret_key", lambda: "sk_test")

    apply_subscription_to_tenant(tid, "sub_inc")
    row = tenants_db.get_tenant(tid)
    assert row is not None
    assert row["tier_id"] == "free"
    assert row["stripe_subscription_id"] == "sub_inc"


def test_async_payment_failed_clears_sub_and_tier(tenant_db: str) -> None:
    tid = tenant_db
    tenants_db.link_stripe_customer(tid, "cus_f")
    tenants_db.set_stripe_subscription_id(tid, "sub_f")
    tenants_db.set_tenant_tier(tid, "indie")
    session = {
        "mode": "subscription",
        "metadata": {"tenant_id": tid},
        "customer": "cus_f",
    }
    handle_checkout_session_async_payment_failed(session)
    row = tenants_db.get_tenant(tid)
    assert row is not None
    assert row["tier_id"] == "free"
    assert row["stripe_subscription_id"] is None


def test_subscription_trial_will_end_posts_notify_url(
    tenant_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STUDIO_TRIAL_END_NOTIFY_WEBHOOK_URL", "https://example.test/hook")
    tid = tenant_db
    tenants_db.link_stripe_customer(tid, "cus_tr")
    sub = {
        "id": "sub_tr",
        "customer": "cus_tr",
        "trial_end": 1700000000,
    }
    with patch("httpx.post") as m_post:
        m_post.return_value.raise_for_status = lambda: None
        handle_subscription_trial_will_end(sub)
        m_post.assert_called_once()
        args, kwargs = m_post.call_args
        assert args[0] == "https://example.test/hook"
        assert kwargs["json"]["tenant_id"] == tid
        assert kwargs["json"]["stripe_subscription_id"] == "sub_tr"


def test_handle_stripe_event_async_payment_succeeded(tenant_db: str) -> None:
    tid = tenant_db
    session = {
        "mode": "subscription",
        "metadata": {"tenant_id": tid},
        "customer": "cus_a",
        "subscription": "sub_a",
    }
    ev = {"type": "checkout.session.async_payment_succeeded", "data": {"object": session}}
    with patch("studio_worker.stripe_billing.apply_subscription_to_tenant") as m:
        handle_stripe_event(ev)
        m.assert_called_once_with(tid, "sub_a")


def test_subscription_deleted_downgrades(tenant_db: str) -> None:
    tid = tenant_db
    tenants_db.link_stripe_customer(tid, "cus_d")
    tenants_db.set_stripe_subscription_id(tid, "sub_d")
    tenants_db.set_tenant_tier(tid, "indie")
    sub = {"id": "sub_d", "customer": "cus_d"}
    handle_subscription_deleted(sub)
    row = tenants_db.get_tenant(tid)
    assert row is not None
    assert row["tier_id"] == "free"
    assert row["stripe_subscription_id"] is None


def test_webhook_construct_event_signature(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(
        "studio_worker.paths.tenants_db_path", lambda: tmp_path / "t.sqlite"
    )
    tenants_db.init_tenants_schema()

    import stripe
    from fastapi.testclient import TestClient

    from studio_worker.api import app

    payload = b'{"id":"evt_1","type":"checkout.session.completed","data":{"object":{}}}'
    event_obj = MagicMock()
    event_obj.type = "checkout.session.completed"
    event_obj.data.object = {"mode": "subscription", "metadata": {}, "customer": None}

    with patch.object(stripe.Webhook, "construct_event", return_value=event_obj):
        with patch("studio_worker.billing_routes.handle_stripe_event") as h:
            c = TestClient(app)
            r = c.post(
                "/api/studio/billing/webhook",
                content=payload,
                headers={"Stripe-Signature": "sig_test"},
            )
            assert r.status_code == 200
            h.assert_called_once()
