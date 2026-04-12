from __future__ import annotations

from studio_worker.mock_spec import build_mock_spec
from studio_worker.validate import validate_asset_spec


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
