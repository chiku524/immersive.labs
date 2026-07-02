"""Tests for Blender mesh post-processing config and runner guards."""

from __future__ import annotations

from pathlib import Path

import pytest

from studio_worker import mesh_export
from studio_worker.mesh_pipeline.config import (
    mesh_collider_export_enabled,
    mesh_lod_ratios,
    mesh_postprocess_enabled,
)


def test_mesh_postprocess_enabled_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDIO_MESH_POSTPROCESS", raising=False)
    assert mesh_postprocess_enabled() is True
    monkeypatch.setenv("STUDIO_MESH_POSTPROCESS", "0")
    assert mesh_postprocess_enabled() is False


def test_mesh_collider_export_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDIO_MESH_COLLIDER_EXPORT", raising=False)
    assert mesh_collider_export_enabled() is True
    monkeypatch.setenv("STUDIO_MESH_COLLIDER_EXPORT", "false")
    assert mesh_collider_export_enabled() is False


def test_mesh_lod_ratios_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDIO_MESH_LODS", raising=False)
    assert mesh_lod_ratios() == []
    monkeypatch.setenv("STUDIO_MESH_LODS", "0.5, 0.25, bad, 1.5, 0.1")
    assert mesh_lod_ratios() == [0.5, 0.25, 0.1]


def test_postprocess_skips_when_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STUDIO_MESH_POSTPROCESS", "0")
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF-binary")
    logs, errs = mesh_export.run_blender_postprocess(input_glb=glb, spec={"poly_budget_tris": 8000})
    assert logs == []
    assert errs == []


def test_postprocess_skips_when_blender_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STUDIO_MESH_POSTPROCESS", "1")
    monkeypatch.setattr(mesh_export, "resolve_blender_executable", lambda: None)
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF-binary")
    logs, errs = mesh_export.run_blender_postprocess(input_glb=glb, spec={"poly_budget_tris": 8000})
    assert errs == []
    assert logs and "Blender not found" in logs[0]


def test_postprocess_skips_when_input_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STUDIO_MESH_POSTPROCESS", "1")
    logs, errs = mesh_export.run_blender_postprocess(
        input_glb=tmp_path / "missing.glb", spec={"poly_budget_tris": 8000}
    )
    assert logs == []
    assert errs == []
