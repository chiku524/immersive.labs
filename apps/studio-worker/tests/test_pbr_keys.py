from __future__ import annotations

from studio_worker.pbr_keys import (
    GENERATED_ROLES,
    mat_name_for_part,
    ordered_pbr_material_bases,
    primary_pbr_material_base,
)


def test_generated_roles() -> None:
    assert "albedo" in GENERATED_ROLES


def test_ordered_bases_dedupes_slot_roles() -> None:
    spec = {
        "variants": [{"variant_id": "default", "label": "A"}],
        "material_slots": [
            {"id": "main", "role": "albedo", "resolution_hint": 512},
            {"id": "main", "role": "normal", "resolution_hint": 512},
            {"id": "trim", "role": "albedo", "resolution_hint": 512},
        ],
    }
    assert ordered_pbr_material_bases(spec) == ["default_main", "default_trim"]


def test_ordered_bases_two_variants() -> None:
    spec = {
        "variants": [
            {"variant_id": "a", "label": "1"},
            {"variant_id": "b", "label": "2"},
        ],
        "material_slots": [
            {"id": "body", "role": "albedo", "resolution_hint": 512},
        ],
    }
    assert ordered_pbr_material_bases(spec) == ["a_body", "b_body"]


def test_primary_fallback() -> None:
    spec = {
        "variants": [{"variant_id": "v1", "label": "x"}],
        "material_slots": [
            {"id": "only_emissive", "role": "emissive", "resolution_hint": 512},
        ],
    }
    assert primary_pbr_material_base(spec) == "v1_only_emissive"


def test_mat_name_for_part() -> None:
    assert mat_name_for_part(["a", "b"], 0) == "a"
    assert mat_name_for_part(["a", "b"], 3) == "b"
    assert mat_name_for_part([], 0) == "default_main"
