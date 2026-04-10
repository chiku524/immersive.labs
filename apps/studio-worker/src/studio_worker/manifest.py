from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_job_manifest(
    assets: list[dict[str, Any]],
    *,
    job_id: str | None = None,
    llm_model: str | None = None,
    image_pipeline: str | None = None,
    mesh_pipeline: str | None = None,
    unity_urp_version: str | None = None,
) -> dict[str, Any]:
    toolchain: dict[str, str] = {}
    if llm_model:
        toolchain["llm_model"] = llm_model
    if image_pipeline:
        toolchain["image_pipeline"] = image_pipeline
    if mesh_pipeline:
        toolchain["mesh_pipeline"] = mesh_pipeline
    urp = unity_urp_version or os.environ.get("STUDIO_UNITY_URP_VERSION")
    if urp:
        toolchain["unity_urp_version"] = urp

    return {
        "manifest_version": "0.1",
        "job_id": job_id or str(uuid.uuid4()),
        "created_at": utc_now_iso(),
        "engine_target": "unity",
        "assets": assets,
        "toolchain": toolchain,
    }
