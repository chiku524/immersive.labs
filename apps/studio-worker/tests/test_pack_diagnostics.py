from __future__ import annotations

from pathlib import Path

from studio_worker.pack_diagnostics import build_pack_diagnostics


def _minimal_spec() -> dict:
    return {
        "asset_id": "test_prop",
        "material_slots": [{"id": "main", "role": "albedo", "resolution_hint": 512}],
        "variants": [{"variant_id": "0", "label": "Base"}],
    }


def test_pack_diagnostics_tripo_fallback_not_marked_textured(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    pack_root.mkdir()
    diag = build_pack_diagnostics(
        spec=_minimal_spec(),
        pack_root=pack_root,
        generate_textures=True,
        export_mesh=True,
        mesh_pipeline="tripo:fallback_blender+ok",
        image_pipeline="tripo:baked_pbr_v1+fallback_blender",
        texture_bind_logs=[],
        texture_bind_errors=[],
        texture_source="tripo",
    )
    assert diag["mesh_tripo_fallback_used"] is True
    assert diag["tripo_mesh_textured"] is False
    assert any("Blender placeholder" in n for n in diag["notes"])


def test_pack_diagnostics_real_tripo_marked_textured(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    pack_root.mkdir()
    diag = build_pack_diagnostics(
        spec=_minimal_spec(),
        pack_root=pack_root,
        generate_textures=True,
        export_mesh=True,
        mesh_pipeline="tripo:text_to_model+ok",
        image_pipeline="tripo:baked_pbr_v1+ok",
        texture_bind_logs=[],
        texture_bind_errors=[],
        texture_source="tripo",
    )
    assert diag["mesh_tripo_fallback_used"] is False
    assert diag["tripo_mesh_textured"] is True
