from __future__ import annotations

from pathlib import Path

import pytest

from studio_worker.pack_writer import write_pack


def _minimal_spec() -> dict:
    return {
        "spec_version": "0.1",
        "asset_id": "test_prop",
        "display_name": "Test Prop",
        "category": "prop",
        "style_preset": "toon_bold",
        "poly_budget_tris": 1200,
        "target_height_m": 1.0,
        "tags": ["test"],
        "material_slots": [
            {"id": "body", "role": "albedo", "resolution_hint": 512},
        ],
        "variants": [{"variant_id": "default", "label": "Default"}],
        "generation": {"source_prompt": "a test prop"},
        "unity": {"import_subfolder": "Props", "collider": "box"},
    }


def test_write_pack_unity_target(tmp_path: Path) -> None:
    out = tmp_path / "unity_pack"
    manifest = write_pack(out, _minimal_spec(), engine_target="unity")
    assert manifest["engine_target"] == "unity"
    assert (out / "UnityImportNotes.md").is_file()
    assert (out / "UnrealImportNotes.md").is_file()
    readme = (out / "README.txt").read_text(encoding="utf-8")
    assert "Unity" in readme
    assert "Unreal" in readme


def test_write_pack_unreal_target(tmp_path: Path) -> None:
    out = tmp_path / "unreal_pack"
    manifest = write_pack(out, _minimal_spec(), engine_target="unreal")
    assert manifest["engine_target"] == "unreal"
    assert (out / "UnrealImportNotes.md").is_file()
    assert (out / "UnityImportNotes.md").is_file()
    readme = (out / "README.txt").read_text(encoding="utf-8")
    assert "Unreal" in readme
    assert "Unity" in readme


def test_write_pack_invalid_engine_target(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="engine_target"):
        write_pack(tmp_path / "bad", _minimal_spec(), engine_target="godot")


def test_write_pack_derives_unreal_block_and_notes(tmp_path: Path) -> None:
    spec = _minimal_spec()
    spec["unity"]["collider"] = "mesh_convex"
    out = tmp_path / "ue_pack"
    write_pack(out, spec, engine_target="unreal", write_spec_json=True)
    # validate_asset_spec runs inside write_pack and derives the unreal block from unity.
    assert spec["unreal"]["collision_complexity"] == "convex"
    assert spec["unreal"]["import_subfolder"] == "Props"
    notes = (out / "UnrealImportNotes.md").read_text(encoding="utf-8")
    assert "collision `convex`" in notes
    assert "import under `Props`" in notes


def test_write_pack_honors_explicit_unreal_block(tmp_path: Path) -> None:
    spec = _minimal_spec()
    spec["unreal"] = {"import_subfolder": "Environment/Kit", "collision_complexity": "complex"}
    out = tmp_path / "ue_pack_explicit"
    write_pack(out, spec, engine_target="unreal")
    assert spec["unreal"]["collision_complexity"] == "complex"
    assert spec["unreal"]["import_subfolder"] == "Environment/Kit"
