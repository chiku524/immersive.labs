from __future__ import annotations

import os

import pytest

from studio_worker.comfy_client import minimal_txt2img_prompt_graph, run_txt2image_workflow


@pytest.mark.gpu_comfy
def test_live_comfy_txt2img_round_trip() -> None:
    """
    Opt-in integration test: full ComfyUI `/prompt` → history → `/view` PNG bytes.
    Requires a reachable ComfyUI with an SD1.5-compatible checkpoint installed.

    Env:
      STUDIO_RUN_GPU_COMFY_TESTS=1
      STUDIO_COMFY_URL — base URL (no trailing slash required)
      STUDIO_COMFY_CHECKPOINT — exact checkpoint file name as in ComfyUI’s loader
      STUDIO_COMFY_STEPS — optional, default 4 (keep low for CI smoke)
    """
    if os.environ.get("STUDIO_RUN_GPU_COMFY_TESTS", "") != "1":
        pytest.skip("Set STUDIO_RUN_GPU_COMFY_TESTS=1 to run live ComfyUI tests.")

    base = os.environ.get("STUDIO_COMFY_URL", "").strip().rstrip("/")
    if not base:
        pytest.skip("Set STUDIO_COMFY_URL to your ComfyUI base URL.")

    ckpt = os.environ.get("STUDIO_COMFY_CHECKPOINT", "").strip()
    if not ckpt:
        pytest.skip(
            "Set STUDIO_COMFY_CHECKPOINT to a checkpoint filename present on the ComfyUI host "
            "(e.g. the name shown in CheckpointLoaderSimple)."
        )

    steps = int(os.environ.get("STUDIO_COMFY_STEPS", "4"))
    wf = minimal_txt2img_prompt_graph(ckpt, steps=steps)
    png = run_txt2image_workflow(wf, base_url=base, wait_timeout_s=float(os.environ.get("STUDIO_COMFY_TIMEOUT_S", "420")))
    assert len(png) > 100
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_minimal_txt2img_graph_shape() -> None:
    g = minimal_txt2img_prompt_graph("dummy.safetensors")
    assert set(g.keys()) == {"1", "2", "3", "4", "5", "6", "7"}
    assert g["1"]["class_type"] == "CheckpointLoaderSimple"
    assert g["7"]["class_type"] == "SaveImage"
