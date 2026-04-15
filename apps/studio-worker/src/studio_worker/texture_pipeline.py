from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from studio_worker.comfy_client import ComfyUIError, comfy_image_wait_timeout_s, run_txt2image_workflow
from studio_worker.pbr_keys import GENERATED_ROLES
from studio_worker.scale_config import (
    comfy_max_concurrent,
    texture_global_max_side,
    texture_style_max_side,
)
from studio_worker.workflow_template import build_albedo_workflow

STYLE_ALBEDO_PREFIX: dict[str, str] = {
    "toon_bold": (
        "bold toon game asset albedo texture, clean value steps, readable forms, "
        "orthographic-friendly, tileable surface, no text, no watermark, "
    ),
    "anime_stylized": (
        "anime-inspired hand-painted albedo texture, stylized surface detail, "
        "clean color regions, game asset, tileable, no text, no watermark, "
    ),
    "realistic_hd_pbr": (
        "photorealistic PBR base color map, detailed realistic surface, subtle wear, "
        "tileable texture, no text, no watermark, ",
    ),
}

STYLE_NORMAL_HINT: dict[str, str] = {
    "toon_bold": "stylized tangent-space normal map, smooth surfaces, soft bumps, ",
    "anime_stylized": "clean anime-style normal map, readable surface breaks, ",
    "realistic_hd_pbr": "high-frequency surface normal detail, realistic micro-variation, ",
}

STYLE_ORM_HINT: dict[str, str] = {
    "toon_bold": "technical ORM mask texture: R ambient occlusion, G roughness, B metallic, flat chart, ",
    "anime_stylized": "ORM technical map: occlusion roughness metallic channels, stylized material response, ",
    "realistic_hd_pbr": "linear ORM packed map: occlusion roughness metallic, photographic PBR helper, ",
}

ROLE_NEGATIVE_EXTRA: dict[str, str] = {
    "albedo": "",
    "normal": "albedo colors, rgb diffuse, skin tones, rainbow, text",
    "orm": "rgb albedo, colorful diffuse, text, rainbow, photo",
    "emissive": "",
    "mask": "",
}

DEFAULT_NEGATIVE = (
    "text, watermark, logo, blurry, lowres, deformed, cropped frame, ui, "
    "multiple objects, character sheet, human face"
)

_ALLOWED_SIDES = (512, 1024, 2048, 4096)


def _snap_side(n: int) -> int:
    n = max(256, int(n))
    return min(_ALLOWED_SIDES, key=lambda x: abs(x - n))


def texture_output_dimensions(spec: dict[str, Any]) -> tuple[int, int]:
    """
    Width/height for Comfy EmptyLatentImage from material_slots resolution_hint,
    clamped by style + STUDIO_TEXTURE_MAX_SIDE / STUDIO_TEXTURE_MAX_SIDE_<STYLE>.
    """
    style = str(spec.get("style_preset", "toon_bold"))
    slots = [s for s in (spec.get("material_slots") or []) if isinstance(s, dict)]
    tex_slots = [s for s in slots if str(s.get("role")) in GENERATED_ROLES]
    hints: list[int] = []
    for s in tex_slots:
        rh = s.get("resolution_hint")
        if isinstance(rh, int):
            hints.append(rh)
        elif isinstance(rh, str) and rh.strip().isdigit():
            hints.append(int(rh.strip()))
    prof = comfy_profile()
    fallback = 1024 if prof == "sdxl" else 512
    requested = max(hints) if hints else fallback
    cap = min(texture_style_max_side(style), texture_global_max_side())
    side = max(256, min(int(requested), cap))
    side = _snap_side(side)
    return side, side


def comfy_profile() -> str:
    return os.environ.get("STUDIO_COMFY_PROFILE", "sd15").lower()


def comfy_checkpoint() -> str:
    return os.environ.get(
        "STUDIO_COMFY_CHECKPOINT",
        "v1-5-pruned-emaonly.safetensors" if comfy_profile() == "sd15" else "sd_xl_base_1.0.safetensors",
    )


def max_texture_images() -> int:
    return max(1, int(os.environ.get("STUDIO_TEXTURE_MAX_IMAGES", "32")))


def _role_positive(style: str, role: str, user_line: str, notes: str) -> str:
    notes = notes.strip()
    if role == "albedo":
        base = STYLE_ALBEDO_PREFIX.get(style, STYLE_ALBEDO_PREFIX["toon_bold"])
        return f"{base}{user_line}. {notes}".strip()
    if role == "normal":
        hint = STYLE_NORMAL_HINT.get(style, STYLE_NORMAL_HINT["realistic_hd_pbr"])
        return (
            f"{hint}seamless tangent-space normal map texture, blue-purple opengl style, "
            f"no albedo color, height-to-normal look, {user_line}. {notes}"
        ).strip()
    if role == "orm":
        hint = STYLE_ORM_HINT.get(style, STYLE_ORM_HINT["realistic_hd_pbr"])
        return (
            f"{hint}no painted colors, neutral grayscale channels, game PBR ORM, {user_line}. {notes}"
        ).strip()
    raise ValueError(f"Unsupported generated role: {role}")


def _negative_for_role(role: str, gen_negative: str | None) -> str:
    parts = [DEFAULT_NEGATIVE]
    extra = ROLE_NEGATIVE_EXTRA.get(role, "")
    if extra:
        parts.append(extra)
    if gen_negative:
        parts.append(gen_negative)
    return ", ".join(p for p in parts if p)


def _emit_texture_progress(
    pack_dir: Path,
    *,
    queue_id: str | None,
    done: int,
    total: int,
    label: str,
    width: int,
    height: int,
) -> None:
    payload = {
        "phase": "textures",
        "done": done,
        "total": total,
        "label": label,
        "width": width,
        "height": height,
    }
    try:
        (pack_dir / "texture_progress.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    if queue_id:
        try:
            from studio_worker.sqlite_queue import update_queue_job_progress

            update_queue_job_progress(queue_id, payload)
        except Exception:
            pass


def _run_one_texture_task(
    item: dict[str, Any],
) -> tuple[int, Path, str]:
    """Worker: queue Comfy, return (sequence index, dest path, log line)."""
    idx = item["idx"]
    wf = item["workflow"]
    base_url = item.get("base_url")
    wait_s = item["wait_timeout_s"]
    dest: Path = item["dest"]

    png = run_txt2image_workflow(
        wf,
        base_url=base_url,
        wait_timeout_s=wait_s,
    )
    dest.write_bytes(png)
    return idx, dest, f"Wrote {dest.name} ({len(png)} bytes)"


def generate_pbr_textures_for_spec(
    spec: dict[str, Any],
    pack_dir: Path,
    *,
    base_url: str | None = None,
    queue_id: str | None = None,
) -> tuple[list[Path], list[str]]:
    """
    For each variant × material slot whose role is albedo, normal, or orm, run ComfyUI txt2img
    and save PNG under pack_dir / Textures / asset_id / as {variant}_{slot}_{role}.png.

    Optional ``queue_id`` updates queue row progress (running jobs) and writes
    ``texture_progress.json`` under the pack folder during execution.
    """
    asset_id = spec.get("asset_id", "asset")
    style = str(spec.get("style_preset", "toon_bold"))
    gen = spec.get("generation") or {}
    user_line = str(gen.get("source_prompt") or asset_id)
    gen_neg = str(gen.get("negative_prompt") or "").strip() or None

    variants = spec.get("variants") or []
    slots = [s for s in (spec.get("material_slots") or []) if isinstance(s, dict)]
    tex_slots = [s for s in slots if str(s.get("role")) in GENERATED_ROLES]
    if not tex_slots:
        return [], ["No albedo/normal/orm material_slots; skipping texture generation."]

    out_dir = pack_dir / "Textures" / asset_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tw, th = texture_output_dimensions(spec)
    prof = comfy_profile()
    ckpt = comfy_checkpoint()
    budget = max_texture_images()
    wait_s = comfy_image_wait_timeout_s()

    tasks: list[dict[str, Any]] = []
    seq = 0
    for v in variants:
        if seq >= budget:
            break
        if not isinstance(v, dict):
            continue
        vid = str(v.get("variant_id") or "default")
        seed = int(v.get("seed") or seq * 7919)

        for slot in tex_slots:
            if seq >= budget:
                break
            role = str(slot.get("role"))
            sid = str(slot.get("id") or "main")
            notes = str(slot.get("notes") or "")
            positive = _role_positive(style, role, user_line, notes)
            negative = _negative_for_role(role, gen_neg)

            prefix_fn = f"im_{asset_id}_{vid}_{sid}_{role}"[:72]
            dest = out_dir / f"{vid}_{sid}_{role}.png"
            wf = build_albedo_workflow(
                profile=prof,
                checkpoint_name=ckpt,
                positive=positive,
                negative=negative,
                seed=seed + seq * 97,
                filename_prefix=prefix_fn,
                width=tw,
                height=th,
            )
            tasks.append(
                {
                    "idx": seq,
                    "workflow": wf,
                    "base_url": base_url,
                    "wait_timeout_s": wait_s,
                    "dest": dest,
                }
            )
            seq += 1

    total = len(tasks)
    if total == 0:
        return [], ["No texture tasks after variant/material expansion."]

    workers = comfy_max_concurrent()
    written: list[Path] = [Path()] * total
    logs: list[str] = [""] * total
    poll_lock = threading.Lock()
    done_count = 0

    def on_progress(label: str) -> None:
        nonlocal done_count
        with poll_lock:
            done_count += 1
            _emit_texture_progress(
                pack_dir,
                queue_id=queue_id,
                done=done_count,
                total=total,
                label=label,
                width=tw,
                height=th,
            )

    if workers <= 1:
        for t in tasks:
            idx, path, line = _run_one_texture_task(t)
            written[idx] = path
            logs[idx] = line
            on_progress(path.name)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_run_one_texture_task, t): t for t in tasks}
            for fut in as_completed(futures):
                idx, path, line = fut.result()
                written[idx] = path
                logs[idx] = line
                on_progress(path.name)

    extra_logs: list[str] = []
    if seq >= budget:
        extra_logs.append(f"Stopped after {budget} images (STUDIO_TEXTURE_MAX_IMAGES).")

    return written, [x for x in logs if x] + extra_logs


def generate_albedo_textures_for_spec(
    spec: dict[str, Any],
    pack_dir: Path,
    *,
    base_url: str | None = None,
    queue_id: str | None = None,
) -> tuple[list[Path], list[str]]:
    """Backward-compatible alias: use generate_pbr_textures_for_spec (all PBR roles)."""
    return generate_pbr_textures_for_spec(spec, pack_dir, base_url=base_url, queue_id=queue_id)
