from __future__ import annotations

from studio_worker.validate import POLY_MAX_BY_PRESET, REQUIRED_MATERIAL_ROLES

STYLE_PRESETS = ("realistic_hd_pbr", "anime_stylized", "toon_bold")
CATEGORIES = ("prop", "environment_piece", "character_base", "material_library")


def system_prompt_for_style(style_preset: str) -> str:
    if style_preset not in STYLE_PRESETS:
        raise ValueError(f"Unknown style_preset: {style_preset}")

    poly_max = POLY_MAX_BY_PRESET[style_preset]
    roles = sorted(REQUIRED_MATERIAL_ROLES[style_preset])

    style_notes = {
        "realistic_hd_pbr": (
            "Target believable PBR: include subtle wear where appropriate; "
            "prefer ORM texture; normal map should support surface detail."
        ),
        "anime_stylized": (
            "Target clean anime-inspired surfaces: readable forms, controlled highlights; "
            "albedo carries most of the look; normal can be subtle."
        ),
        "toon_bold": (
            "Target bold toon readability: simplified albedo, strong silhouette-friendly forms; "
            "avoid noisy micro-detail in textures."
        ),
    }[style_preset]

    return f"""You are a technical game art director. Output a single JSON object only (no markdown, no commentary) that matches this contract:

Required top-level keys:
- spec_version: exactly "0.1"
- asset_id: lowercase snake_case, only [a-z0-9_], e.g. prop_crate_wood_01
- display_name: short human title
- category: one of {list(CATEGORIES)}
- style_preset: must be exactly "{style_preset}" (do not change it)
- poly_budget_tris: integer, must be <= {poly_max} for this style
- target_height_m: positive number (meters), typically 0.5–3.0 for props; use 1.0 if scale is unknown (never null)
- palette: optional array of #RRGGBB strings for color locking
- tags: non-empty array of short strings
- material_slots: array; each item has id, role, resolution_hint as JSON integer (512|1024|2048|4096), not a string, optional notes
  Required roles for this style: {roles}
- variants: at least one item with variant_id and label; optional integer seed per variant
- generation: object with source_prompt (echo the user's creative brief faithfully), optional negative_prompt (must be a JSON string if present, never null — omit the key or use an empty string if unused), optional reference_assets array
- unity: import_subfolder relative path using forward slashes, no ".." (e.g. Props/Crates), collider one of box|capsule|mesh_convex|none

Style direction for this preset: {style_notes}

Rules:
- Use forward slashes in unity.import_subfolder.
- Keep JSON strictly valid: double quotes, no trailing commas.
- material_slots resolution_hint must be one of 512, 1024, 2048, 4096 (JSON numbers).
"""


def user_prompt_block(user_prompt: str, category: str) -> str:
    return (
        f"Category (fixed for this request): {category}\n\n"
        f"Creative brief:\n{user_prompt.strip()}\n"
    )
