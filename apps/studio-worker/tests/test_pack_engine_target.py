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
