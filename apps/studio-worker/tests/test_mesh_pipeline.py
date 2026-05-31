from __future__ import annotations

from pathlib import Path

import httpx
from unittest.mock import MagicMock, patch

import pytest
import respx

from studio_worker.mesh_pipeline.config import TRIPO_API_BASE
from studio_worker.mesh_pipeline.providers.tripo import TripoMeshProvider, prompt_from_spec
from studio_worker.mesh_pipeline.runner import FALLBACK_PIPELINE_ID, resolve_mesh_provider, try_export_mesh_for_pack


def test_prompt_from_spec_prefers_source_prompt() -> None:
    spec = {
        "asset_id": "crate_01",
        "generation": {"source_prompt": "rusty iron crate"},
    }
    assert prompt_from_spec(spec) == "rusty iron crate"


def test_resolve_blender_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDIO_MESH_PROVIDER", raising=False)
    p = resolve_mesh_provider()
    assert p.pipeline_id == "blender:export_mesh.py"


def test_resolve_tripo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_MESH_PROVIDER", "tripo")
    p = resolve_mesh_provider()
    assert p.pipeline_id == "tripo:text_to_model"


def test_tripo_missing_api_key_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    (root / "spec.json").write_text('{"asset_id": "x"}', encoding="utf-8")
    monkeypatch.setenv("STUDIO_MESH_PROVIDER", "tripo")
    monkeypatch.delenv("STUDIO_TRIPO_API_KEY", raising=False)

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
            logs, errs, pipeline = try_export_mesh_for_pack(root, {"asset_id": "x"})

    assert not errs
    assert pipeline == FALLBACK_PIPELINE_ID
    assert logs


@respx.mock
def test_tripo_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "pack2"
    root.mkdir()
    (root / "spec.json").write_text(
        '{"asset_id": "barrel_01", "generation": {"source_prompt": "wooden barrel"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("STUDIO_MESH_PROVIDER", "tripo")
    monkeypatch.setenv("STUDIO_TRIPO_API_KEY", "test-key")
    monkeypatch.setenv("STUDIO_TRIPO_POLL_INTERVAL_S", "0.01")
    monkeypatch.setenv("STUDIO_TRIPO_TIMEOUT_S", "30")

    task_id = "task-abc"
    respx.post(f"{TRIPO_API_BASE}/task").mock(
        return_value=httpx.Response(200, json={"data": {"task_id": task_id}})
    )
    respx.get(f"{TRIPO_API_BASE}/task/{task_id}").mock(
        side_effect=[
            httpx.Response(200, json={"data": {"status": "running"}}),
            httpx.Response(
                200,
                json={
                    "data": {
                        "status": "success",
                        "output": {"pbr_model": "https://cdn.example.com/model.glb"},
                    }
                },
            ),
        ]
    )
    respx.get("https://cdn.example.com/model.glb").mock(
        return_value=httpx.Response(200, content=b"glTF-binary")
    )

    provider = TripoMeshProvider()
    logs, errs = provider.export_for_pack(root, {"asset_id": "barrel_01"})
    assert not errs
    assert logs
    glb = root / "Models" / "barrel_01" / "barrel_01.glb"
    assert glb.is_file()
    assert glb.read_bytes() == b"glTF-binary"
