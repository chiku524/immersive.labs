from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from studio_worker.paths import comfy_workflows_dir, studio_worker_root
from studio_worker.texture_pipeline import comfy_checkpoint, comfy_profile


def write_pack_attribution(
    pack_dir: Path,
    *,
    spec: dict[str, Any],
    manifest: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> None:
    """
    Writes ATTRIBUTION.md + licenses.json into a pack for traceability (Phase 6).
    """
    pack_dir = pack_dir.resolve()
    pack_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=UTC).replace(microsecond=0).isoformat()
    prof = comfy_profile()
    ckpt = comfy_checkpoint()
    wf_dir = comfy_workflows_dir()
    workflow_files = sorted(p.name for p in wf_dir.glob("*.api.json")) if wf_dir.is_dir() else []

    lines = [
        "# Attribution & tooling",
        "",
        f"- **Generated at (UTC):** {now}",
        f"- **Job / manifest id:** `{manifest.get('job_id', '')}`",
        f"- **Asset id:** `{spec.get('asset_id', '')}`",
        f"- **Style preset:** `{spec.get('style_preset', '')}`",
        "",
        "## Models & checkpoints (user-supplied)",
        "",
        f"- **ComfyUI profile:** `{prof}`",
        f"- **Checkpoint name (env STUDIO_COMFY_CHECKPOINT):** `{ckpt}`",
        "",
        "You are responsible for licensing and permitted use of any checkpoint, LoRA, or custom node. ",
        "This repository does not redistribute model weights.",
        "",
        "## Graphs shipped in-repo",
        "",
        *[f"- `{fn}`" for fn in workflow_files],
        "",
        "## LLM",
        "",
        f"- **Recorded:** `{manifest.get('toolchain', {}).get('llm_model', 'n/a')}`",
        "",
        "## Third-party",
        "",
        "- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) (MIT)",
        "- [FastAPI](https://fastapi.tiangolo.com/) (MIT)",
        "- [jsonschema](https://github.com/python-jsonschema/jsonschema) (MIT)",
        "",
        "## Immersive Labs studio worker",
        "",
        f"- **Package root:** `{studio_worker_root()}`",
        "",
    ]

    (pack_dir / "ATTRIBUTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    licenses: dict[str, Any] = {
        "generated_at_utc": now,
        "job_id": manifest.get("job_id"),
        "asset_id": spec.get("asset_id"),
        "comfyui": {
            "profile": prof,
            "checkpoint_filename": ckpt,
            "workflow_files": workflow_files,
        },
        "llm": {
            "toolchain_llm_model": manifest.get("toolchain", {}).get("llm_model"),
            "spec_meta": meta or {},
        },
        "environment_snapshot": {
            k: os.environ.get(k)
            for k in (
                "STUDIO_OLLAMA_MODEL",
                "STUDIO_COMFY_URL",
                "STUDIO_COMFY_PROFILE",
                "STUDIO_COMFY_CHECKPOINT",
            )
        },
    }
    (pack_dir / "licenses.json").write_text(json.dumps(licenses, indent=2) + "\n", encoding="utf-8")
