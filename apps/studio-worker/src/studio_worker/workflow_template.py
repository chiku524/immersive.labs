from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from studio_worker.paths import comfy_workflows_dir


def load_sd15_template() -> dict[str, Any]:
    path = comfy_workflows_dir() / "sd15_albedo_v1.api.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_sdxl_template() -> dict[str, Any]:
    path = comfy_workflows_dir() / "sdxl_albedo_v1.api.json"
    return json.loads(path.read_text(encoding="utf-8"))


def build_albedo_workflow(
    *,
    profile: str,
    checkpoint_name: str,
    positive: str,
    negative: str,
    seed: int,
    filename_prefix: str,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    profile = profile.lower().strip()
    if profile == "sdxl":
        wf = copy.deepcopy(load_sdxl_template())
        if steps is None:
            steps = 28
        if cfg is None:
            cfg = 6.5
        default_w, default_h = 1024, 1024
    else:
        wf = copy.deepcopy(load_sd15_template())
        if steps is None:
            steps = 24
        if cfg is None:
            cfg = 7.0
        default_w, default_h = 512, 512

    wf["1"]["inputs"]["ckpt_name"] = checkpoint_name
    wf["2"]["inputs"]["width"] = int(width) if width is not None else default_w
    wf["2"]["inputs"]["height"] = int(height) if height is not None else default_h
    wf["3"]["inputs"]["text"] = positive
    wf["4"]["inputs"]["text"] = negative
    wf["5"]["inputs"]["seed"] = int(seed) & 0xFFFFFFFFFFFFFFFF
    wf["5"]["inputs"]["steps"] = int(steps)
    wf["5"]["inputs"]["cfg"] = float(cfg)
    wf["7"]["inputs"]["filename_prefix"] = filename_prefix[:80]
    return wf
