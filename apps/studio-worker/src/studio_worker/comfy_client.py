from __future__ import annotations

import json
import time
import uuid
from typing import Any

import httpx


class ComfyUIError(RuntimeError):
    pass


# Default when STUDIO_COMFY_URL is unset: hosted ComfyUI (Immersive Labs). Override with
# STUDIO_COMFY_URL=http://127.0.0.1:8188 for a local ComfyUI, or http://127.0.0.1:8188 on the
# worker VM when ComfyUI runs on the same machine (see GCE instance metadata).
DEFAULT_COMFY_BASE_URL = "https://comfy.immersivelabs.space"


def comfy_base_url() -> str:
    import os

    return os.environ.get("STUDIO_COMFY_URL", DEFAULT_COMFY_BASE_URL).rstrip("/")


def comfy_reachability(*, base_url: str | None = None) -> dict[str, Any]:
    """
    Probe ComfyUI HTTP API (same check as GET /api/studio/comfy-status).
    """
    base = (base_url or comfy_base_url()).rstrip("/")
    try:
        r = httpx.get(f"{base}/system_stats", timeout=5.0)
        ok = r.status_code < 400
        return {"reachable": ok, "url": base, "detail": None if ok else r.text[:200]}
    except httpx.RequestError as e:
        return {"reachable": False, "url": base, "detail": str(e)}


def queue_prompt(prompt_graph: dict[str, Any], *, base_url: str | None = None) -> str:
    base = base_url or comfy_base_url()
    client_id = str(uuid.uuid4())
    try:
        r = httpx.post(
            f"{base}/prompt",
            json={"prompt": prompt_graph, "client_id": client_id},
            timeout=60.0,
        )
    except httpx.RequestError as e:
        raise ComfyUIError(f"Cannot reach ComfyUI at {base}: {e}") from e
    if r.status_code >= 400:
        raise ComfyUIError(f"ComfyUI /prompt {r.status_code}: {r.text[:800]}")
    data = r.json()
    pid = data.get("prompt_id")
    if not isinstance(pid, str):
        raise ComfyUIError(f"Unexpected /prompt response: {json.dumps(data)[:400]}")
    return pid


def fetch_history(*, base_url: str | None = None) -> dict[str, Any]:
    base = base_url or comfy_base_url()
    try:
        r = httpx.get(f"{base}/history", timeout=60.0)
    except httpx.RequestError as e:
        raise ComfyUIError(f"Cannot reach ComfyUI at {base}: {e}") from e
    if r.status_code >= 400:
        raise ComfyUIError(f"ComfyUI /history {r.status_code}: {r.text[:400]}")
    data = r.json()
    if not isinstance(data, dict):
        raise ComfyUIError("ComfyUI /history returned non-object JSON")
    return data


def wait_for_prompt(
    prompt_id: str,
    *,
    base_url: str | None = None,
    timeout_s: float = 420.0,
    poll_interval_s: float = 0.75,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        hist = fetch_history(base_url=base_url)
        last = hist.get(prompt_id)
        if isinstance(last, dict):
            if last.get("outputs"):
                return last
            status = last.get("status")
            if isinstance(status, dict) and status.get("status_str") in ("error", "failed"):
                msgs = status.get("messages") or []
                raise ComfyUIError(f"ComfyUI execution failed: {msgs[:3]}")
        time.sleep(poll_interval_s)
    raise TimeoutError(f"Timed out waiting for ComfyUI prompt_id={prompt_id}; last={last!r}")


def first_output_image(entry: dict[str, Any]) -> tuple[str, str, str]:
    outputs = entry.get("outputs") or {}
    if not isinstance(outputs, dict):
        raise ComfyUIError("History entry missing outputs")
    for _node_id, node_out in outputs.items():
        if not isinstance(node_out, dict):
            continue
        images = node_out.get("images") or []
        if not images:
            continue
        img0 = images[0]
        if not isinstance(img0, dict):
            continue
        fn = img0.get("filename")
        sub = img0.get("subfolder") or ""
        typ = img0.get("type") or "output"
        if isinstance(fn, str):
            return fn, str(sub), str(typ)
    raise ComfyUIError(f"No images in history outputs: {json.dumps(outputs)[:400]}")


def download_image(
    filename: str,
    *,
    subfolder: str = "",
    type_: str = "output",
    base_url: str | None = None,
) -> bytes:
    base = base_url or comfy_base_url()
    params = {"filename": filename, "subfolder": subfolder, "type": type_}
    try:
        r = httpx.get(f"{base}/view", params=params, timeout=120.0)
    except httpx.RequestError as e:
        raise ComfyUIError(f"Cannot download image from ComfyUI: {e}") from e
    if r.status_code >= 400:
        raise ComfyUIError(f"ComfyUI /view {r.status_code}: {r.text[:200]}")
    return r.content


def run_txt2image_workflow(
    workflow: dict[str, Any],
    *,
    base_url: str | None = None,
    wait_timeout_s: float = 420.0,
) -> bytes:
    pid = queue_prompt(workflow, base_url=base_url)
    entry = wait_for_prompt(pid, base_url=base_url, timeout_s=wait_timeout_s)
    fn, sub, typ = first_output_image(entry)
    return download_image(fn, subfolder=sub, type_=typ, base_url=base_url)


def minimal_txt2img_prompt_graph(
    ckpt_name: str,
    *,
    positive: str = "a simple red cube on gray background, product photo",
    negative: str = "low quality, blurry, watermark",
    seed: int = 42,
    width: int = 512,
    height: int = 512,
    steps: int = 4,
    cfg: float = 7.0,
) -> dict[str, Any]:
    """
    Minimal SD1.5-style API graph for ComfyUI `/prompt`.
    `ckpt_name` must match a file listed in ComfyUI’s checkpoint loader (e.g. env STUDIO_COMFY_CHECKPOINT).
    """
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt_name},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": max(1, int(steps)),
                "cfg": float(cfg),
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "immersive_studio_gpu_test",
                "images": ["6", 0],
            },
        },
    }
