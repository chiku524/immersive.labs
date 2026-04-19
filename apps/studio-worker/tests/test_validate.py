from __future__ import annotations

from typing import Any

from studio_worker.mock_spec import build_mock_spec
from studio_worker.validate import load_asset_validator, validate_asset_spec


def test_mock_spec_validates_toon() -> None:
    spec = build_mock_spec(
        user_prompt="test crate",
        category="prop",
        style_preset="toon_bold",
    )
    validate_asset_spec(spec)


def test_mock_spec_validates_anime() -> None:
    spec = build_mock_spec(
        user_prompt="energy sword",
        category="prop",
        style_preset="anime_stylized",
    )
    validate_asset_spec(spec)


def test_target_height_m_null_coerced_before_validation() -> None:
    spec = build_mock_spec(
        user_prompt="crate",
        category="prop",
        style_preset="toon_bold",
    )
    spec["target_height_m"] = None
    validate_asset_spec(spec)
    assert spec["target_height_m"] == 1.0


def test_generation_negative_prompt_null_becomes_empty_string() -> None:
    spec = build_mock_spec(
        user_prompt="crate",
        category="prop",
        style_preset="toon_bold",
    )
    spec["generation"]["negative_prompt"] = None
    validate_asset_spec(spec)
    assert spec["generation"]["negative_prompt"] == ""


def test_json_schema_accepts_literal_string_resolution_enum_without_coercion() -> None:
    """Defense in depth: schema allows canonical string enums before normalize runs."""
    spec = build_mock_spec(
        user_prompt="crate",
        category="prop",
        style_preset="toon_bold",
    )
    spec["material_slots"][0]["resolution_hint"] = "2048"
    load_asset_validator().validate(spec)


def test_material_slot_resolution_hint_string_coerced_to_int() -> None:
    spec = build_mock_spec(
        user_prompt="crate",
        category="prop",
        style_preset="toon_bold",
    )
    spec["material_slots"][0]["resolution_hint"] = "2048"
    validate_asset_spec(spec)
    assert spec["material_slots"][0]["resolution_hint"] == 2048


def test_material_slot_resolution_hint_embedded_in_label_string() -> None:
    spec = build_mock_spec(
        user_prompt="crate",
        category="prop",
        style_preset="toon_bold",
    )
    spec["material_slots"][0]["resolution_hint"] = "texture 2048 (2k)"
    validate_asset_spec(spec)
    assert spec["material_slots"][0]["resolution_hint"] == 2048


def test_material_slot_resolution_hint_json_quoted_number_string() -> None:
    spec = build_mock_spec(
        user_prompt="crate",
        category="prop",
        style_preset="toon_bold",
    )
    spec["material_slots"][0]["resolution_hint"] = '"2048"'
    validate_asset_spec(spec)
    assert spec["material_slots"][0]["resolution_hint"] == 2048


def test_poly_budget_tri_alias_normalized() -> None:
    spec = build_mock_spec(
        user_prompt="crate",
        category="prop",
        style_preset="toon_bold",
    )
    del spec["poly_budget_tris"]
    spec["poly_budget_tri"] = 8000
    validate_asset_spec(spec)
    assert spec["poly_budget_tris"] == 8000
    assert "poly_budget_tri" not in spec


def test_llm_variation_presets_and_generation_shaped_variants() -> None:
    """Regression: Ollama emitted variation_presets and put generation fields under variants."""
    spec: dict[str, Any] = {
        "spec_version": "0.1",
        "asset_id": "prop_crate_wood_01",
        "display_name": "Deep Sea Critter",
        "category": "environment_piece",
        "style_preset": "anime_stylized",
        "target_height_m": 1.0,
        "variants": [
            {
                "source_prompt": "Echo the user's creative brief faithfully",
                "reference_assets": [{"id": "box"}, {"id": "capsule"}],
                "reference_assets_array": [{"id": "box"}],
                "reference_assets_array_notes": "",
            },
            {
                "source_prompt": "Keep the JSON compact",
                "reference_assets": [{"id": "mesh_convex"}, {"id": "none"}],
            },
        ],
        "variation_presets": [{"name": "animé stylized"}],
        "poly_budget_tris": 2500,
        "material_slots": [
            {"id": "albedo_slot_0", "role": "albedo", "resolution_hint": 1024},
            {"id": "normal_slot_1", "role": "normal", "resolution_hint": 1024},
        ],
        "tags": ["generated"],
    }
    validate_asset_spec(spec)
    assert "variation_presets" not in spec
    assert spec.get("unity", {}).get("import_subfolder")
    assert spec.get("unity", {}).get("collider") == "box"
    assert isinstance(spec.get("generation"), dict)
    assert spec["generation"]["source_prompt"]
    assert {v["variant_id"] for v in spec["variants"]} == {"default", "alt"}
    roles = {s["role"] for s in spec["material_slots"]}
    assert roles == {"albedo", "normal", "orm"}


def test_llm_extra_keys_on_variants_stripped() -> None:
    spec = build_mock_spec(
        user_prompt="crate",
        category="prop",
        style_preset="toon_bold",
    )
    spec["variants"][0]["source_prompt"] = "should not appear here"
    validate_asset_spec(spec)
    assert "source_prompt" not in spec["variants"][0]


def test_llm_misplaces_slots_in_palette_recover_tags_collider() -> None:
    """Regression: Ollama sometimes emits poly_budget_tri, dicts under palette, omits tags/collider."""
    spec: dict[str, Any] = {
        "spec_version": "0.1",
        "asset_id": "prop_crate_wood_01",
        "display_name": "Deep Sea Critter",
        "category": "prop",
        "style_preset": "toon_bold",
        "poly_budget_tri": 5000,
        "target_height_m": 1.0,
        "palette": [
            {"id": "albedo", "resolution_hinit": 512},
            {"id": "orm", "resolution_hinit": 1024},
        ],
        "variants": [
            {"variant_id": "1", "label": "Low Resolution"},
            {"variant_id": "2", "label": "High Resolution"},
        ],
        "generation": {
            "source_prompt": "Echo the user's creative brief faithfully",
            "reference_assets": ["props/crates"],
        },
        "unity": {"import_subfolder": "Prop/Crates"},
    }
    validate_asset_spec(spec)
    assert spec["poly_budget_tris"] == 5000
    assert "palette" not in spec
    assert spec["unity"]["collider"] == "box"
    assert spec["tags"] == ["generated"]
    roles = {s["role"] for s in spec["material_slots"]}
    assert roles == {"albedo", "orm"}
