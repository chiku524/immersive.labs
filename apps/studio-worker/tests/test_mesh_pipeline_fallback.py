from __future__ import annotations

import pytest
import respx
import httpx
from pathlib import Path
from unittest.mock import MagicMock, patch

from studio_worker.mesh_pipeline.config import TRIPO_API_BASE
from studio_worker.mesh_pipeline.runner import FALLBACK_PIPELINE_ID, try_export_mesh_for_pack
from studio_worker.mesh_pipeline.tripo_errors import is_tripo_credit_error, is_tripo_fallback_eligible_error


def test_credit_error_detection() -> None:
    assert is_tripo_credit_error(['Tripo HTTP 403: {"code":2010,"message":"You don\'t have enough credit"}'])
    assert is_tripo_fallback_eligible_error(["Tripo mesh export requires STUDIO_TRIPO_API_KEY"])
    assert is_tripo_fallback_eligible_error(["Tripo HTTP 500: internal error"])
    assert not is_tripo_credit_error(["Tripo HTTP 500: internal error"])
    assert not is_tripo_fallback_eligible_error(["Tripo task banned: policy violation"])


@respx.mock
def test_tripo_http_500_fallback_to_blender(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    (root / "spec.json").write_text('{"asset_id": "crate_01"}', encoding="utf-8")
    monkeypatch.setenv("STUDIO_MESH_PROVIDER", "tripo")
    monkeypatch.setenv("STUDIO_TRIPO_API_KEY", "test-key")

    respx.post(f"{TRIPO_API_BASE}/task").mock(return_value=httpx.Response(500, text="internal error"))

    fake_blender = tmp_path / "blender_stub"
    fake_blender.write_bytes(b"")
    monkeypatch.setenv("STUDIO_BLENDER_BIN", str(fake_blender))

    def run_side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
        out_i = cmd.index("--output") + 1
        p = Path(cmd[out_i])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"glb")
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=run_side_effect):
        with patch(
            "studio_worker.mesh_export.blender_export_script_path",
            return_value=tmp_path / "export_mesh.py",
        ):
            (tmp_path / "export_mesh.py").write_text("#", encoding="utf-8")
            logs, errs, pipeline = try_export_mesh_for_pack(root, {"asset_id": "crate_01"})

    assert not errs
    assert pipeline == FALLBACK_PIPELINE_ID
    assert (root / "Models" / "crate_01" / "crate_01.glb").is_file()
    assert any("tripo mesh unavailable" in line.lower() for line in logs)


@respx.mock
def test_tripo_credit_fallback_to_blender(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    (root / "spec.json").write_text(
        '{"asset_id": "barrel_01", "generation": {"source_prompt": "wooden barrel"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("STUDIO_MESH_PROVIDER", "tripo")
    monkeypatch.setenv("STUDIO_TRIPO_API_KEY", "test-key")

    respx.post(f"{TRIPO_API_BASE}/task").mock(
        return_value=httpx.Response(
            403,
            json={"code": 2010, "message": "You don't have enough credit to create this task"},
        )
    )

    fake_blender = tmp_path / "blender_stub"
    fake_blender.write_bytes(b"")
    monkeypatch.setenv("STUDIO_BLENDER_BIN", str(fake_blender))

    def run_side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
        out_i = cmd.index("--output") + 1
        p = Path(cmd[out_i])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"glb")
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("subprocess.run", side_effect=run_side_effect):
        with patch(
            "studio_worker.mesh_export.blender_export_script_path",
            return_value=tmp_path / "export_mesh.py",
        ):
            (tmp_path / "export_mesh.py").write_text("#", encoding="utf-8")
            logs, errs, pipeline = try_export_mesh_for_pack(root, {"asset_id": "barrel_01"})

    assert not errs
    assert pipeline == FALLBACK_PIPELINE_ID
    assert any(
        "tripo mesh unavailable" in line.lower() or "as fallback" in line.lower() for line in logs
    )
    assert (root / "Models" / "barrel_01" / "barrel_01.glb").is_file()
