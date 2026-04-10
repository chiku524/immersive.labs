from __future__ import annotations

from typing import Any

from studio_worker.job_runner import run_studio_job
from studio_worker.tenant_context import RequestTenant
from studio_worker.tiers import get_tier


def execute_queued_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Maps queue payload JSON to run_studio_job kwargs. Expected keys mirror RunJobRequest
    plus optional comfy_base_url, tenant_id, tier_id, limits_enforced, credits_precharged.
    """
    request_tenant: RequestTenant | None = None
    tid = payload.get("tenant_id")
    if tid is not None and str(tid).strip():
        request_tenant = RequestTenant(
            tenant_id=str(tid).strip(),
            tier=get_tier(str(payload.get("tier_id") or "free")),
            tier_id=str(payload.get("tier_id") or "free"),
            limits_enforced=bool(payload.get("limits_enforced", False)),
            credits_precharged=bool(payload.get("credits_precharged", False)),
        )
    return run_studio_job(
        user_prompt=str(payload["user_prompt"]),
        category=str(payload.get("category", "prop")),
        style_preset=str(payload.get("style_preset", "toon_bold")),
        use_mock=bool(payload.get("mock", False)),
        generate_textures=bool(payload.get("generate_textures", False)),
        unity_urp_hint=str(
            payload.get("unity_urp_hint", "6000.0.x LTS (pin when smoke-tested)")
        ),
        comfy_base_url=payload.get("comfy_base_url"),
        request_tenant=request_tenant,
        export_mesh=bool(payload.get("export_mesh", False)),
    )
