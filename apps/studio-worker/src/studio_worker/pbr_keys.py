"""
PBR material base keys: `{variant_id}_{slot_id}` aligned with texture filenames and Unity Lit mats.

Used by the ComfyUI texture loop, Blender export_mesh (via sys.path), and matches Unity importer ordering.
"""

from __future__ import annotations

from typing import Any

GENERATED_ROLES = frozenset({"albedo", "normal", "orm"})


def ordered_pbr_material_bases(spec: dict[str, Any]) -> list[str]:
    """
    Unique {variant_id}_{slot_id} keys in variant order, then material slot order
    (matches worker `generate_pbr_textures_for_spec` and Unity `GetOrderedPbrMaterialBases`).
    """
    variants = spec.get("variants") or []
    slots = spec.get("material_slots") or []
    tex_slots: list[dict[str, Any]] = []
    for s in slots:
        if not isinstance(s, dict):
            continue
        role = str(s.get("role") or "").lower()
        if role in GENERATED_ROLES:
            tex_slots.append(s)

    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        vid = str(v.get("variant_id") or "default")
        for slot in tex_slots:
            sid = str(slot.get("id") or "main")
            key = f"{vid}_{sid}"
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


def primary_pbr_material_base(spec: dict[str, Any]) -> str:
    """First PBR base from ordering, or a conservative default when slots are missing."""
    bases = ordered_pbr_material_bases(spec)
    if bases:
        return bases[0]
    variants = spec.get("variants") or []
    v0 = variants[0] if variants else {}
    vid = str(v0.get("variant_id") or "default")
    slots = spec.get("material_slots") or []
    if slots and isinstance(slots[0], dict):
        return f"{vid}_{str(slots[0].get('id') or 'main')}"
    return f"{vid}_main"


def mat_name_for_part(bases: list[str], part_index: int) -> str:
    """Rotate through PBR bases for multi-part placeholder meshes."""
    if not bases:
        return "default_main"
    return bases[part_index % len(bases)]
