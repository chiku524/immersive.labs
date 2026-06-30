from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from studio_worker.mesh_pipeline.config import (
    TRIPO_API_BASE,
    tripo_api_key,
    tripo_model_version,
    tripo_pbr_enabled,
    tripo_poll_interval_s,
    tripo_texture_enabled,
    tripo_timeout_s,
)

_log = logging.getLogger("studio.mesh.tripo")


def prompt_from_spec(spec: dict[str, Any]) -> str:
    gen = spec.get("generation") or {}
    source = str(gen.get("source_prompt") or "").strip()
    if source:
        return source[:1024]
    for key in ("display_name", "asset_id"):
        val = str(spec.get(key) or "").strip()
        if val:
            return val[:1024]
    return "game prop"


def _pick_model_url(output: Any) -> str | None:
    if not isinstance(output, dict):
        return None
    for key in ("pbr_model", "model", "base_model", "glb", "model_url"):
        val = output.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    for val in output.values():
        if isinstance(val, str) and val.startswith("http") and ".glb" in val.lower():
            return val
    return None


class TripoMeshProvider:
    """Paid/hosted text-to-3D via Tripo OpenAPI (enable when STUDIO_TRIPO_API_KEY is set)."""

    pipeline_id = "tripo:text_to_model"

    def export_for_pack(
        self,
        pack_root: Path,
        spec: dict[str, Any],
    ) -> tuple[list[str], list[str]]:
        api_key = tripo_api_key()
        if not api_key:
            return [], [
                "Tripo mesh export requires STUDIO_TRIPO_API_KEY. "
                "Get a key at https://platform.tripo3d.ai/api-keys — Blender placeholder "
                "will be used as fallback when STUDIO_MESH_FALLBACK=1 (default)."
            ]

        asset_id = str(spec.get("asset_id") or "asset")
        out_glb = pack_root / "Models" / asset_id / f"{asset_id}.glb"
        out_glb.parent.mkdir(parents=True, exist_ok=True)

        prompt = prompt_from_spec(spec)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        texture = tripo_texture_enabled()
        payload: dict[str, Any] = {
            "type": "text_to_model",
            "prompt": prompt,
            "model_version": tripo_model_version(),
            "auto_size": True,
            "texture": texture,
            "pbr": tripo_pbr_enabled() if texture else False,
        }

        consumed_credit: int | None = None
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                create = client.post(f"{TRIPO_API_BASE}/task", headers=headers, json=payload)
                create.raise_for_status()
                body = create.json()
                task_id = (body.get("data") or {}).get("task_id")
                if not task_id:
                    return [], [f"Tripo task create returned no task_id: {body!r}"]

                _log.info("tripo_task_created task_id=%s asset_id=%s", task_id, asset_id)
                deadline = time.monotonic() + tripo_timeout_s()
                model_url: str | None = None

                while time.monotonic() < deadline:
                    poll = client.get(f"{TRIPO_API_BASE}/task/{task_id}", headers=headers)
                    poll.raise_for_status()
                    data = poll.json().get("data") or {}
                    status = str(data.get("status") or "").lower()

                    if status == "success":
                        raw_credit = data.get("consumed_credit")
                        if isinstance(raw_credit, int):
                            consumed_credit = raw_credit
                        elif isinstance(raw_credit, str) and raw_credit.isdigit():
                            consumed_credit = int(raw_credit)
                        model_url = _pick_model_url(data.get("output"))
                        if not model_url:
                            return [], [f"Tripo task succeeded but no model URL in output: {data.get('output')!r}"]
                        break
                    if status in ("failed", "cancelled", "banned"):
                        detail = data.get("message") or data.get("error") or status
                        return [], [f"Tripo task {status}: {detail}"]

                    time.sleep(tripo_poll_interval_s())
                else:
                    return [], [f"Tripo task timed out after {tripo_timeout_s():.0f}s (task_id={task_id})"]

                dl = client.get(model_url, follow_redirects=True)
                dl.raise_for_status()
                out_glb.write_bytes(dl.content)
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:500] if e.response is not None else str(e)
            return [], [f"Tripo HTTP {e.response.status_code if e.response else '?'}: {detail}"]
        except httpx.HTTPError as e:
            return [], [f"Tripo request failed: {e}"]

        host = urlparse(model_url or "").netloc or "tripo"
        size = out_glb.stat().st_size
        credit_note = (
            f", consumed_credit={consumed_credit}"
            if consumed_credit is not None
            else ""
        )
        texture_note = "texture+on" if texture else "texture+off (credit saver)"
        return [
            f"Tripo text_to_model → {out_glb.name} ({size} bytes from {host}, "
            f"{texture_note}{credit_note}, prompt={prompt[:80]!r})"
        ], []
