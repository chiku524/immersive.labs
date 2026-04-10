from __future__ import annotations

import re
from typing import Any

from studio_worker.prompts import CATEGORIES
from studio_worker.validate import POLY_MAX_BY_PRESET, REQUIRED_MATERIAL_ROLES


def _slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:48] or "asset").strip("_")


def build_mock_spec(
    *,
    user_prompt: str,
    category: str,
    style_preset: str,
) -> dict[str, Any]:
    if category not in CATEGORIES:
        raise ValueError(f"Invalid category: {category}")
    if style_preset not in POLY_MAX_BY_PRESET:
        raise ValueError(f"Invalid style_preset: {style_preset}")

    aid = f"prop_{_slugify(user_prompt)}"
    if not aid.replace("_", "").isalnum():
        aid = "prop_mock_asset"
    roles = sorted(REQUIRED_MATERIAL_ROLES[style_preset])
    poly_default = min(4000, POLY_MAX_BY_PRESET[style_preset])

    slot_id_by_role = {
        "albedo": "main",
        "normal": "normal",
        "orm": "orm",
        "emissive": "emissive",
        "mask": "mask",
    }
    slots: list[dict[str, Any]] = []
    res = 1024 if style_preset != "realistic_hd_pbr" else 2048
    for role in roles:
        slots.append(
            {
                "id": slot_id_by_role.get(role, role),
                "role": role,
                "resolution_hint": res,
                "notes": "Mock slot for pipeline wiring",
            }
        )

    return {
        "spec_version": "0.1",
        "asset_id": aid,
        "display_name": user_prompt.strip()[:80] or "Mock asset",
        "category": category,
        "style_preset": style_preset,
        "poly_budget_tris": poly_default,
        "target_height_m": 1.0,
        "tags": ["mock", category, style_preset],
        "material_slots": slots,
        "variants": [
            {"variant_id": "default", "label": "Default", "seed": 42},
            {"variant_id": "alt", "label": "Alternate tint", "seed": 43},
        ],
        "generation": {
            "source_prompt": user_prompt.strip(),
            "negative_prompt": "blurry, low poly glitch, watermark",
        },
        "unity": {
            "import_subfolder": "Props/Generated",
            "collider": "box",
        },
    }
