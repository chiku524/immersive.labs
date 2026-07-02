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


def _write_pack(root: Path, folder: str, *, asset_id: str, collider: str, hull: bool) -> None:
    import json

    job = root / folder
    (job / "Models" / asset_id).mkdir(parents=True, exist_ok=True)
    (job / "manifest.json").write_text(
        json.dumps(
            {
                "engine_target": "unreal",
                "assets": [{"asset_id": asset_id, "unity": {"collider": collider}}],
            }
        ),
        encoding="utf-8",
    )
    if hull:
        (job / "Models" / asset_id / f"{asset_id}_collider.glb").write_bytes(b"glTF")


def test_collider_report_flags_missing_and_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from studio_worker import cli

    jobs = tmp_path / "jobs"
    jobs.mkdir()
    _write_pack(jobs, "job_ok", asset_id="prop_a", collider="mesh_convex", hull=True)
    _write_pack(jobs, "job_missing", asset_id="prop_b", collider="mesh_convex", hull=False)
    _write_pack(jobs, "job_box", asset_id="prop_c", collider="box", hull=False)

    monkeypatch.setattr(cli, "jobs_root", lambda: jobs, raising=False)
    # jobs_root is imported inside the function from studio_worker.paths; patch there too.
    import studio_worker.paths as paths

    monkeypatch.setattr(paths, "jobs_root", lambda: jobs)

    cli._doctor_recent_collider_report(limit=10)
    out = capsys.readouterr().out
    assert "job_ok" in out and "1/1 convex assets have _collider.glb — OK" in out
    assert "job_missing" in out and "0/1 convex assets have _collider.glb — MISSING hull(s)" in out
    assert "job_box" in out and "no convex-collision assets" in out
