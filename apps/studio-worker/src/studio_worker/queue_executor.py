from __future__ import annotations

from typing import Any

from studio_worker.job_runner import run_studio_job
from studio_worker.ollama_client import effective_use_mock
from studio_worker.tenant_context import RequestTenant
from studio_worker.tiers import get_tier


def execute_queued_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Maps queue payload JSON to run_studio_job kwargs. Expected keys mirror RunJobRequest
    plus optional comfy_base_url, tenant_id, tier_id, limits_enforced, credits_precharged.
    Internal-only ``_queue_id`` is injected by queue workers for in-flight progress updates.
    """
    p = dict(payload)
    qid = p.pop("_queue_id", None)
    request_tenant: RequestTenant | None = None
    tid = p.get("tenant_id")
    if tid is not None and str(tid).strip():
        request_tenant = RequestTenant(
            tenant_id=str(tid).strip(),
            tier=get_tier(str(p.get("tier_id") or "free")),
            tier_id=str(p.get("tier_id") or "free"),
            limits_enforced=bool(p.get("limits_enforced", False)),
            credits_precharged=bool(p.get("credits_precharged", False)),
        )
    return run_studio_job(
        user_prompt=str(p["user_prompt"]),
        category=str(p.get("category", "prop")),
        style_preset=str(p.get("style_preset", "toon_bold")),
        use_mock=effective_use_mock(bool(p.get("mock", False))),
        generate_textures=bool(p.get("generate_textures", False)),
        unity_urp_hint=str(
            p.get("unity_urp_hint", "6000.0.x LTS (pin when smoke-tested)")
        ),
        comfy_base_url=p.get("comfy_base_url"),
        request_tenant=request_tenant,
        export_mesh=bool(p.get("export_mesh", False)),
        queue_id=str(qid).strip() if qid else None,
    )
