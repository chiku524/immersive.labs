from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from studio_worker.comfy_client import ComfyUIError, comfy_image_wait_timeout_s, run_txt2image_workflow
from studio_worker.pbr_keys import GENERATED_ROLES
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


def generate_pbr_textures_for_spec(
    spec: dict[str, Any],
    pack_dir: Path,
    *,
    base_url: str | None = None,
) -> tuple[list[Path], list[str]]:
    """
    For each variant × material slot whose role is albedo, normal, or orm, run ComfyUI txt2img
    and save PNG under pack_dir / Textures / asset_id / as {variant}_{slot}_{role}.png.
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

    written: list[Path] = []
    logs: list[str] = []
    budget = max_texture_images()
    count = 0

    for v in variants:
        if count >= budget:
            logs.append(f"Stopped after {budget} images (STUDIO_TEXTURE_MAX_IMAGES).")
            break
        if not isinstance(v, dict):
            continue
        vid = str(v.get("variant_id") or "default")
        seed = int(v.get("seed") or count * 7919)

        for slot in tex_slots:
            if count >= budget:
                break
            role = str(slot.get("role"))
            sid = str(slot.get("id") or "main")
            notes = str(slot.get("notes") or "")
            positive = _role_positive(style, role, user_line, notes)
            negative = _negative_for_role(role, gen_neg)

            prefix_fn = f"im_{asset_id}_{vid}_{sid}_{role}"[:72]
            wf = build_albedo_workflow(
                profile=comfy_profile(),
                checkpoint_name=comfy_checkpoint(),
                positive=positive,
                negative=negative,
                seed=seed + count * 97,
                filename_prefix=prefix_fn,
            )

            try:
                png = run_txt2image_workflow(
                    wf,
                    base_url=base_url,
                    wait_timeout_s=comfy_image_wait_timeout_s(),
                )
            except (ComfyUIError, TimeoutError) as e:
                raise RuntimeError(f"ComfyUI failed for {vid}/{sid}/{role}: {e}") from e

            dest = out_dir / f"{vid}_{sid}_{role}.png"
            dest.write_bytes(png)
            written.append(dest)
            logs.append(f"Wrote {dest.name} ({len(png)} bytes)")
            count += 1

    return written, logs


def generate_albedo_textures_for_spec(
    spec: dict[str, Any],
    pack_dir: Path,
    *,
    base_url: str | None = None,
) -> tuple[list[Path], list[str]]:
    """Backward-compatible alias: use generate_pbr_textures_for_spec (all PBR roles)."""
    return generate_pbr_textures_for_spec(spec, pack_dir, base_url=base_url)
