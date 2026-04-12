from __future__ import annotations

import json
import re
from pathlib import Path
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
    _coerce_target_height_m(spec)
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


def normalize_asset_spec(spec: dict[str, Any]) -> None:
    """Coerce common LLM quirks in-place before schema validation."""
    _coerce_target_height_m(spec)
    pb = spec.get("poly_budget_tris")
    if isinstance(pb, float):
        spec["poly_budget_tris"] = int(pb)
    for slot in spec.get("material_slots") or []:
        if not isinstance(slot, dict):
            continue
        rh = slot.get("resolution_hint")
        if isinstance(rh, float):
            slot["resolution_hint"] = int(rh)


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
