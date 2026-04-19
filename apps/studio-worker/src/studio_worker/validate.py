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

_ALLOWED_TOP_LEVEL = frozenset({
    "spec_version",
    "asset_id",
    "display_name",
    "category",
    "style_preset",
    "poly_budget_tris",
    "target_height_m",
    "palette",
    "tags",
    "material_slots",
    "variants",
    "generation",
    "unity",
})


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


def _ensure_required_material_roles(spec: dict[str, Any]) -> None:
    """Append default slots when the LLM omits roles required for the chosen style_preset."""
    style = spec.get("style_preset")
    if style not in REQUIRED_MATERIAL_ROLES:
        return
    slots = spec.get("material_slots")
    if not isinstance(slots, list):
        return
    roles_present = {s.get("role") for s in slots if isinstance(s, dict)}
    missing = REQUIRED_MATERIAL_ROLES[style] - roles_present
    if not missing:
        return
    base_res = 1024
    for s in slots:
        if isinstance(s, dict) and isinstance(s.get("resolution_hint"), int):
            base_res = s["resolution_hint"]
            break
    for role in sorted(missing):
        slots.append(
            {
                "id": f"{role}_slot_{len(slots)}",
                "role": role,
                "resolution_hint": base_res,
            }
        )


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


def _reference_asset_entry_to_strings(item: Any) -> list[str]:
    if isinstance(item, str) and item.strip():
        return [item.strip()]
    if isinstance(item, dict):
        for key in ("path", "uri", "id", "asset", "name"):
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                return [val.strip()]
        for val in item.values():
            if isinstance(val, str) and val.strip():
                return [val.strip()]
            break
    return []


def _collect_reference_assets_from_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    acc: list[str] = []
    for item in raw:
        acc.extend(_reference_asset_entry_to_strings(item))
    return acc


def _normalize_variant_list(variants: list[Any]) -> list[dict[str, Any]] | None:
    """
    If every item has variant_id + label, drop extra keys (LLMs often add source_prompt, etc.).
    Otherwise return None so callers can run fragment recovery.
    """
    out: list[dict[str, Any]] = []
    for i, v in enumerate(variants):
        if not isinstance(v, dict):
            return None
        vid_raw = v.get("variant_id")
        lbl_raw = v.get("label")
        if not isinstance(vid_raw, str) or not vid_raw.strip():
            return None
        if not isinstance(lbl_raw, str) or not lbl_raw.strip():
            return None
        item: dict[str, Any] = {
            "variant_id": vid_raw.strip(),
            "label": lbl_raw.strip(),
        }
        if "seed" in v:
            s = v["seed"]
            if isinstance(s, bool):
                pass
            elif isinstance(s, (int, float)):
                item["seed"] = int(s)
            elif isinstance(s, str):
                try:
                    item["seed"] = int(float(s.strip()))
                except ValueError:
                    pass
        out.append(item)
    return out if out else None


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _recover_generation_from_malformed_variants(spec: dict[str, Any]) -> None:
    """
    Models sometimes emit ``generation``-shaped objects inside ``variants`` (and add
    ``variation_presets``). Merge prompts/refs into ``generation`` and replace
    ``variants`` with a sane default list when normalization is impossible.
    """
    variants = spec.get("variants")
    if not isinstance(variants, list) or not variants:
        return
    normalized = _normalize_variant_list(variants)
    if normalized is not None:
        spec["variants"] = normalized
        return

    source_prompts: list[str] = []
    neg_prompts: list[str] = []
    ref_assets: list[str] = []

    for v in variants:
        if not isinstance(v, dict):
            continue
        sp = v.get("source_prompt")
        if isinstance(sp, str) and sp.strip():
            source_prompts.append(sp.strip())
        np = v.get("negative_prompt")
        if isinstance(np, str) and np.strip():
            neg_prompts.append(np.strip())
        for key in ("reference_assets", "reference_assets_array"):
            ref_assets.extend(_collect_reference_assets_from_list(v.get(key)))

    gen = spec.get("generation")
    if not isinstance(gen, dict):
        gen = {}

    if not (isinstance(gen.get("source_prompt"), str) and gen["source_prompt"].strip()):
        merged = " ".join(source_prompts).strip()
        if not merged:
            dn = spec.get("display_name")
            merged = dn.strip() if isinstance(dn, str) and dn.strip() else "Generated asset"
        gen["source_prompt"] = merged

    if "negative_prompt" not in gen or gen.get("negative_prompt") is None:
        gen["negative_prompt"] = neg_prompts[0] if neg_prompts else ""

    if gen.get("reference_assets") is None and ref_assets:
        gen["reference_assets"] = _dedupe_preserve_order(ref_assets)

    spec["generation"] = gen
    spec["variants"] = [
        {"variant_id": "default", "label": "Default", "seed": 42},
        {"variant_id": "alt", "label": "Alternate", "seed": 43},
    ]


def _sanitize_generation_object(spec: dict[str, Any]) -> None:
    """Keep only schema-allowed generation keys; coerce reference_assets to string paths."""
    gen = spec.get("generation")
    if not isinstance(gen, dict):
        return
    out: dict[str, Any] = {}
    sp = gen.get("source_prompt")
    if isinstance(sp, str) and sp.strip():
        out["source_prompt"] = sp.strip()
    np = gen.get("negative_prompt")
    if np is None:
        out["negative_prompt"] = ""
    elif isinstance(np, str):
        out["negative_prompt"] = np
    else:
        out["negative_prompt"] = ""
    ra = gen.get("reference_assets")
    if isinstance(ra, list):
        strings = _collect_reference_assets_from_list(ra)
        if strings:
            out["reference_assets"] = _dedupe_preserve_order(strings)
    spec["generation"] = out


def _strip_disallowed_top_level_keys(spec: dict[str, Any]) -> None:
    for k in list(spec.keys()):
        if k not in _ALLOWED_TOP_LEVEL:
            spec.pop(k, None)


def _ensure_generation_present(spec: dict[str, Any]) -> None:
    gen = spec.get("generation")
    if isinstance(gen, dict):
        sp = gen.get("source_prompt")
        if isinstance(sp, str) and sp.strip():
            if "negative_prompt" not in gen or gen.get("negative_prompt") is None:
                gen["negative_prompt"] = ""
            spec["generation"] = gen
            return
    dn = spec.get("display_name")
    prompt = dn.strip() if isinstance(dn, str) and dn.strip() else "Generated asset"
    spec["generation"] = {"source_prompt": prompt, "negative_prompt": ""}


def _ensure_unity_present(spec: dict[str, Any]) -> None:
    u = spec.get("unity")
    if isinstance(u, dict):
        sub = u.get("import_subfolder")
        coll = u.get("collider")
        if (
            isinstance(sub, str)
            and sub.strip()
            and ".." not in sub
            and not sub.startswith(("/", "\\"))
            and coll in _UNITY_COLLIDERS
        ):
            return
    subfolder = "Props/Generated"
    if isinstance(u, dict):
        sub = u.get("import_subfolder")
        if (
            isinstance(sub, str)
            and sub.strip()
            and ".." not in sub
            and not sub.startswith(("/", "\\"))
        ):
            subfolder = sub.strip()
    spec["unity"] = {"import_subfolder": subfolder, "collider": "box"}


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
    _recover_generation_from_malformed_variants(spec)
    _sanitize_generation_object(spec)
    _strip_disallowed_top_level_keys(spec)
    _ensure_generation_present(spec)
    _ensure_unity_present(spec)
    _coerce_target_height_m(spec)
    _coerce_generation_negative_prompt(spec)
    _recover_material_slots_from_misplaced_palette(spec)
    _coerce_material_slot_resolution_hints(spec)
    _ensure_required_material_roles(spec)
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
