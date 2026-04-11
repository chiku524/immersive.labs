from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from studio_worker.mesh_export import (
    apply_mesh_toolchain_to_manifest,
    resolve_blender_executable,
    run_blender_placeholder_export,
    try_export_placeholder_for_pack,
)


def test_run_blender_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text('{"asset_id": "test_crate", "target_height_m": 1}', encoding="utf-8")
    out_glb = tmp_path / "out.glb"
    fake_blender = tmp_path / "blender_stub"
    fake_blender.write_bytes(b"")
    monkeypatch.setenv("STUDIO_BLENDER_BIN", str(fake_blender))

    def run_side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
        out_i = cmd.index("--output") + 1
        p = Path(cmd[out_i])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"glb")
        return MagicMock(returncode=0, stderr="", stdout="ok")

    with patch("studio_worker.mesh_export.blender_export_script_path", return_value=tmp_path / "export_mesh.py"):
        (tmp_path / "export_mesh.py").write_text("# stub", encoding="utf-8")
        with patch("subprocess.run", side_effect=run_side_effect):
            ok, msg = run_blender_placeholder_export(spec_json_path=spec, output_glb_path=out_glb)
    assert ok
    assert "Wrote" in msg


def test_try_export_pack_integration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    (root / "spec.json").write_text(
        '{"asset_id": "prop_01", "target_height_m": 1.2}',
        encoding="utf-8",
    )
    fake_blender = tmp_path / "blender_stub2"
    fake_blender.write_bytes(b"")
    monkeypatch.setenv("STUDIO_BLENDER_BIN", str(fake_blender))

    def run_side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
        out_i = cmd.index("--output") + 1
        p = Path(cmd[out_i])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"glb")
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=run_side_effect):
        with patch("studio_worker.mesh_export.blender_export_script_path", return_value=tmp_path / "s.py"):
            (tmp_path / "s.py").write_text("#", encoding="utf-8")
            logs, errs = try_export_placeholder_for_pack(
                root,
                {"asset_id": "prop_01"},
            )
    assert not errs
    assert logs


def test_apply_manifest_mesh_ok() -> None:
    m: dict = {"toolchain": {}}
    apply_mesh_toolchain_to_manifest(m, ok=True)
    assert m["toolchain"]["mesh_pipeline"] == "blender:export_mesh.py+ok"


def test_resolve_blender_windows_program_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    bf = tmp_path / "Blender Foundation" / "Blender 4.2"
    bf.mkdir(parents=True)
    exe = bf / "blender.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.delenv("STUDIO_BLENDER_BIN", raising=False)
    with patch("studio_worker.mesh_export.shutil.which", return_value=None):
        assert resolve_blender_executable() == str(exe)
