"""Discover and merge Immersive Labs sidecar PBR PNG groups."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from studio_worker.pbr_keys import ordered_pbr_material_bases

_PBR_FILE_RE = re.compile(r"^(?P<base>.+)_(?P<role>albedo|normal|orm)$", re.IGNORECASE)


def discover_texture_groups(tex_dir: Path) -> dict[str, dict[str, Path]]:
    groups: dict[str, dict[str, Path]] = {}
    if not tex_dir.is_dir():
        return groups
    for png in sorted(tex_dir.glob("*.png")):
        m = _PBR_FILE_RE.match(png.stem)
        if not m:
            continue
        base = m.group("base")
        role = m.group("role").lower()
        groups.setdefault(base, {})[role] = png
    return groups


def _variant_prefix(material_base: str) -> str:
    for suffix in ("_main", "_orm", "_normal"):
        if material_base.endswith(suffix):
            return material_base[: -len(suffix)]
    return material_base


def merge_split_slot_groups(groups: dict[str, dict[str, Path]]) -> dict[str, dict[str, Path]]:
    """
    Merge albedo and ORM PNGs that landed on different PBR bases when the LLM used
    separate material slot ids (e.g. ``main`` + ``orm`` -> ``*_main_albedo`` + ``*_orm_orm``).
    """
    merged = {base: dict(roles) for base, roles in groups.items()}
    albedo_bases = [base for base, roles in groups.items() if "albedo" in roles]
    orm_by_base = {base: roles["orm"] for base, roles in groups.items() if "orm" in roles}

    for albedo_base in albedo_bases:
        if "orm" in merged[albedo_base]:
            continue
        prefix = _variant_prefix(albedo_base)
        matched_orm: Path | None = None
        for orm_base, orm_path in orm_by_base.items():
            orm_prefix = _variant_prefix(orm_base)
            if orm_prefix == prefix or orm_base.startswith(prefix + "_") or albedo_base.startswith(orm_prefix + "_"):
                matched_orm = orm_path
                break
        if matched_orm is None and orm_by_base:
            matched_orm = next(iter(orm_by_base.values()))
        if matched_orm is not None:
            merged[albedo_base]["orm"] = matched_orm

    return merged


def resolve_textures_for_material_bases(
    spec: dict[str, Any],
    tex_dir: Path,
) -> dict[str, dict[str, Path]]:
    raw = discover_texture_groups(tex_dir)
    if not raw:
        return {}
    merged = merge_split_slot_groups(raw)
    bases = ordered_pbr_material_bases(spec)
    if not bases:
        return merged
    out: dict[str, dict[str, Path]] = {}
    for base in bases:
        if base in merged and "albedo" in merged[base]:
            out[base] = merged[base]
    if out:
        return out
    for base, roles in merged.items():
        if "albedo" in roles:
            out[base] = roles
    return out


def diagnose_sidecar_pbr(spec: dict[str, Any], pack_root: Path) -> dict[str, Any]:
    asset_id = str(spec.get("asset_id") or "asset")
    tex_dir = pack_root / "Textures" / asset_id
    glb_path = pack_root / "Models" / asset_id / f"{asset_id}.glb"
    raw = discover_texture_groups(tex_dir)
    merged = merge_split_slot_groups(raw)
    resolved = resolve_textures_for_material_bases(spec, tex_dir)

    incomplete_bases = [
        base
        for base, roles in raw.items()
        if "albedo" in roles and "orm" not in roles
    ]
    split_slot_detected = bool(incomplete_bases) and any("orm" in roles for roles in raw.values())
    complete_bases = [
        base
        for base, roles in resolved.items()
        if "albedo" in roles
    ]

    return {
        "asset_id": asset_id,
        "glb_present": glb_path.is_file(),
        "sidecar_png_count": sum(len(files) for files in raw.values()),
        "raw_texture_bases": sorted(raw.keys()),
        "merged_complete_bases": complete_bases,
        "split_slot_detected": split_slot_detected,
        "ready_for_texture_bind": glb_path.is_file() and bool(complete_bases),
    }
