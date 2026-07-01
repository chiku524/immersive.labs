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
- asset_id: lowercase snake_case, only [a-z0-9_]; derive from the creative brief (e.g. prop_medieval_tower_01 for a tower prop). Never copy placeholder examples verbatim.
- display_name: short human title
- category: one of {list(CATEGORIES)}
- style_preset: must be exactly "{style_preset}" (do not change it)
- poly_budget_tris: integer triangle budget (note the final **s** in ``tris`` — not ``poly_budget_tri``), must be <= {poly_max} for this style
- target_height_m: positive number (meters). Props: typically 0.5–3.0; environment pieces / towers / buildings: often 4–15; use 1.0 if scale is unknown (never null)
- palette: optional array of #RRGGBB strings only (color locking). Never put material slot objects here — they belong only in material_slots.
- tags: non-empty array of short strings
- material_slots: array; each item has id (JSON string, e.g. "main" — never a number), role, resolution_hint as JSON integer (512|1024|2048|4096), not a string, optional notes
  Required roles for this style: {roles}
- variants: at least one item with variant_id and label; optional integer seed per variant. Never put source_prompt, reference_assets, or notes inside variants — those belong only under generation.
- generation: object with source_prompt (echo the user's creative brief faithfully), optional negative_prompt (must be a JSON string if present, never null — omit the key or use an empty string if unused), optional reference_assets array of strings (paths/ids), not objects
- unity: import_subfolder relative path using forward slashes, no ".." — match the asset (e.g. Environment/Towers, Props/Structures). Never use generic crate examples unless the brief is a crate.

Style direction for this preset: {style_notes}

Keep the JSON compact: short strings, no markdown fences, no commentary outside the object.

Rules:
- Do not add any top-level keys beyond this list (no variation_presets, no reference_assets_array, no commentary fields).
- Use forward slashes in unity.import_subfolder.
- asset_id and unity.import_subfolder must reflect the user's brief, not schema examples.
- Keep JSON strictly valid: double quotes, no trailing commas.
- material_slots resolution_hint must be one of 512, 1024, 2048, 4096 (JSON numbers).
"""


def user_prompt_block(user_prompt: str, category: str) -> str:
    return (
        f"Category (fixed for this request): {category}\n\n"
        f"Creative brief:\n{user_prompt.strip()}\n"
    )
