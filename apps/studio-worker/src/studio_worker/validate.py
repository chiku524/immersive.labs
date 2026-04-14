from __future__ import annotations

import json
import re
from pathlib import Path
from collections.abc import Mapping
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from studio_worker.paths import asset_spec_schema_path

ASSET_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
PALETTE_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")

POLY_MAX_BY_PRESET: dict[str, int] = {
    "toon_bold": 12_000,
    "anime_stylized": 25_000,
    "realistic_hd_pbr": 80_000,
}

REQUIRED_MATERIAL_ROLES: dict[str, set[str]] = {
    "toon_bold": {"albedo", "orm"},
    "anime_stylized": {"albedo", "orm", "normal"},
    "realistic_hd_pbr": {"albedo", "normal", "orm"},
}

RESOLUTION_HINT_ALLOWED: tuple[int, ...] = (512, 1024, 2048, 4096)
_RESOLUTION_HINT_TOKEN = re.compile(r"\b(512|1024|2048|4096)\b")

_MATERIAL_ROLE_SET = frozenset({"albedo", "normal", "orm", "emissive", "mask"})
_UNITY_COLLIDERS = frozenset({"box", "capsule", "mesh_convex", "none"})
_POLY_BUDGET_ALIASES = ("poly_budget_tri", "poly_budget_triangle")


def load_asset_validator() -> Draft202012Validator:
    schema_path = asset_spec_schema_path()
    if not schema_path.is_file():
        raise FileNotFoundError(
            f"JSON Schema not found at {schema_path}. Set STUDIO_REPO_ROOT if the monorepo moved."
        )
    with schema_path.open(encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema)


def validate_json_schema(spec: dict[str, Any]) -> None:
    # Always coerce here too: callers must not skip normalize_asset_spec, but
    # long-lived uvicorn/Docker processes often run stale code until restart.
    apply_llm_json_coercions(spec)
    validator = load_asset_validator()
    validator.validate(spec)


def validate_business_rules(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    style = spec.get("style_preset")
    if style not in POLY_MAX_BY_PRESET:
        return [f"Unknown style_preset: {style!r}"]
    poly = spec.get("poly_budget_tris")
    if isinstance(poly, int) and poly > POLY_MAX_BY_PRESET[style]:
        errors.append(
            f"poly_budget_tris {poly} exceeds maximum {POLY_MAX_BY_PRESET[style]} for {style}"
        )

    asset_id = spec.get("asset_id", "")
    if not isinstance(asset_id, str) or not ASSET_ID_PATTERN.fullmatch(asset_id):
        errors.append("asset_id must match ^[a-z0-9_]+$")

    unity = spec.get("unity") or {}
    sub = unity.get("import_subfolder", "")
    if not isinstance(sub, str) or ".." in sub or sub.startswith(("/", "\\")):
        errors.append("unity.import_subfolder must be relative with no '..' segments")

    palette = spec.get("palette")
    if palette is not None:
        if not isinstance(palette, list):
            errors.append("palette must be an array of #RRGGBB strings")
        else:
            for i, c in enumerate(palette):
                if not isinstance(c, str) or not PALETTE_PATTERN.fullmatch(c):
                    errors.append(f"palette[{i}] must be a #RRGGBB hex color")

    slots = spec.get("material_slots") or []
    if isinstance(slots, list) and style in REQUIRED_MATERIAL_ROLES:
        roles = {s.get("role") for s in slots if isinstance(s, dict)}
        needed = REQUIRED_MATERIAL_ROLES[style]
        missing = needed - roles
        if missing:
            errors.append(
                f"material_slots missing required roles for {style}: {sorted(missing)}"
            )

    return errors


def _coerce_target_height_m(spec: dict[str, Any]) -> None:
    """
    LLMs often emit target_height_m: null or omit it; schema requires a positive number when present.
    Coerce null / invalid / non-positive to 1.0 (matches mock_spec + Blender fallback).
    """
    if "target_height_m" not in spec:
        return
    raw = spec["target_height_m"]
    if raw is None:
        spec["target_height_m"] = 1.0
        return
    if isinstance(raw, str):
        try:
            raw = float(raw.strip())
        except ValueError:
            spec["target_height_m"] = 1.0
            return
    if isinstance(raw, bool):
        spec["target_height_m"] = 1.0
        return
    if isinstance(raw, (int, float)):
        v = float(raw)
        if v <= 0 or v != v:
            spec["target_height_m"] = 1.0
        else:
            spec["target_height_m"] = v
        return
    spec["target_height_m"] = 1.0


def _coerce_generation_negative_prompt(spec: dict[str, Any]) -> None:
    """Schema requires generation.negative_prompt to be a string when present; LLMs emit null."""
    gen = spec.get("generation")
    if not isinstance(gen, dict) or "negative_prompt" not in gen:
        return
    raw = gen["negative_prompt"]
    if raw is None:
        gen["negative_prompt"] = ""
    elif not isinstance(raw, str):
        gen["negative_prompt"] = ""


def _snap_resolution_hint(value: int) -> int:
    if value in RESOLUTION_HINT_ALLOWED:
        return value
    return min(RESOLUTION_HINT_ALLOWED, key=lambda x: abs(x - value))


def _parse_resolution_hint(raw: Any) -> int:
    if isinstance(raw, bool):
        return 1024
    if isinstance(raw, (int, float)):
        return _snap_resolution_hint(int(raw))
    if isinstance(raw, str):
        s = (
            raw.strip()
            .lower()
            .replace("px", "")
            .strip('"')
            .strip("'")
            .replace("\u201c", "")
            .replace("\u201d", "")
        )
        m = _RESOLUTION_HINT_TOKEN.search(s)
        if m:
            return int(m.group(1))
        try:
            v = int(float(s))
        except ValueError:
            return 1024
        return _snap_resolution_hint(v)
    return 1024


def _material_slots_to_plain_dicts(spec: dict[str, Any]) -> None:
    """Ensure each slot is a plain dict so in-place coercion always sticks."""
    raw = spec.get("material_slots")
    if not isinstance(raw, list):
        return
    out: list[Any] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(item)
        elif isinstance(item, Mapping):
            out.append(dict(item))
        else:
            out.append(item)
    spec["material_slots"] = out


def _coerce_material_slot_resolution_hints(spec: dict[str, Any]) -> None:
    """resolution_hint must be JSON integer in {512,1024,2048,4096}; models often emit \"2048\"."""
    _material_slots_to_plain_dicts(spec)
    for slot in spec.get("material_slots") or []:
        if not isinstance(slot, dict) or "resolution_hint" not in slot:
            continue
        slot["resolution_hint"] = _parse_resolution_hint(slot["resolution_hint"])


def _rename_poly_budget_aliases(spec: dict[str, Any]) -> None:
    """LLMs often emit ``poly_budget_tri`` instead of ``poly_budget_tris``."""
    for alt in _POLY_BUDGET_ALIASES:
        if alt not in spec:
            continue
        raw = spec.pop(alt)
        if spec.get("poly_budget_tris") is not None:
            continue
        try:
            if isinstance(raw, bool):
                raise ValueError
            spec["poly_budget_tris"] = int(float(str(raw).strip()))
        except (TypeError, ValueError):
            pass


def _role_from_palette_dict(item: dict[str, Any]) -> str | None:
    role = item.get("role")
    if isinstance(role, str) and role.strip().lower() in _MATERIAL_ROLE_SET:
        return role.strip().lower()
    rid = item.get("id")
    if isinstance(rid, str) and rid.strip().lower() in _MATERIAL_ROLE_SET:
        return rid.strip().lower()
    return None


def _recover_material_slots_from_misplaced_palette(spec: dict[str, Any]) -> None:
    """
    Models sometimes put slot-shaped objects under ``palette`` (which must only be #RRGGBB strings).
    Recover ``material_slots`` when missing/empty and strip the invalid palette.
    """
    pal = spec.get("palette")
    if not isinstance(pal, list) or not pal:
        return
    if all(isinstance(x, str) for x in pal):
        return
    slots: list[dict[str, Any]] = []
    for i, item in enumerate(pal):
        if not isinstance(item, dict):
            continue
        role = _role_from_palette_dict(item)
        if role is None:
            continue
        res_raw = (
            item.get("resolution_hint")
            or item.get("resolution_hinit")
            or item.get("resolution")
            or item.get("res")
        )
        hint = _parse_resolution_hint(res_raw)
        sid = item.get("id")
        if isinstance(sid, str) and sid.strip() and sid.strip().lower() not in _MATERIAL_ROLE_SET:
            slot_id = sid.strip()
        else:
            slot_id = f"{role}_slot_{i}"
        slot: dict[str, Any] = {"id": slot_id, "role": role, "resolution_hint": hint}
        notes = item.get("notes")
        if isinstance(notes, str) and notes.strip():
            slot["notes"] = notes.strip()
        slots.append(slot)

    existing = spec.get("material_slots")
    if slots and (not isinstance(existing, list) or len(existing) == 0):
        spec["material_slots"] = slots

    if any(isinstance(x, dict) for x in pal):
        spec.pop("palette", None)


def _default_tags_if_missing(spec: dict[str, Any]) -> None:
    raw = spec.get("tags")
    if isinstance(raw, list):
        cleaned = [x.strip() for x in raw if isinstance(x, str) and x.strip()]
        if cleaned:
            spec["tags"] = cleaned
            return
    spec["tags"] = ["generated"]


def _default_unity_collider(spec: dict[str, Any]) -> None:
    unity = spec.get("unity")
    if not isinstance(unity, dict):
        return
    c = unity.get("collider")
    if c not in _UNITY_COLLIDERS:
        unity["collider"] = "box"


def apply_llm_json_coercions(spec: dict[str, Any]) -> None:
    """Normalize common LLM JSON quirks before JSON Schema validation."""
    if not isinstance(spec, dict):
        return
    _rename_poly_budget_aliases(spec)
    _coerce_target_height_m(spec)
    _coerce_generation_negative_prompt(spec)
    _recover_material_slots_from_misplaced_palette(spec)
    _coerce_material_slot_resolution_hints(spec)
    _default_tags_if_missing(spec)
    _default_unity_collider(spec)


def normalize_asset_spec(spec: dict[str, Any]) -> None:
    """Coerce common LLM quirks in-place before schema validation."""
    apply_llm_json_coercions(spec)
    pb = spec.get("poly_budget_tris")
    if isinstance(pb, float):
        spec["poly_budget_tris"] = int(pb)
    elif isinstance(pb, str):
        try:
            spec["poly_budget_tris"] = int(float(pb.strip()))
        except ValueError:
            pass


def validate_asset_spec(spec: dict[str, Any]) -> None:
    normalize_asset_spec(spec)
    validate_json_schema(spec)
    biz = validate_business_rules(spec)
    if biz:
        raise ValueError("Business rule violations:\n- " + "\n- ".join(biz))


def load_spec_document(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("spec"), dict):
        return data["spec"]
    if not isinstance(data, dict):
        raise ValueError("Spec file must contain a JSON object")
    return data


def validate_asset_spec_file(path: Path) -> dict[str, Any]:
    spec = load_spec_document(path)
    validate_asset_spec(spec)
    return spec
