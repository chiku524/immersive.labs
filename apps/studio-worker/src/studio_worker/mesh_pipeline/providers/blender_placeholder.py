from __future__ import annotations

from pathlib import Path
from typing import Any

from studio_worker.mesh_export import run_blender_placeholder_export


class BlenderPlaceholderProvider:
    """Free local path: headless Blender procedural mesh from spec (Phase 3 placeholder)."""

    pipeline_id = "blender:export_mesh.py"

    def export_for_pack(
        self,
        pack_root: Path,
        spec: dict[str, Any],
    ) -> tuple[list[str], list[str]]:
        spec_path = pack_root / "spec.json"
        if not spec_path.is_file():
            return [], ["Mesh export skipped: spec.json not found in pack root"]

        asset_id = str(spec.get("asset_id") or "asset")
        out_glb = pack_root / "Models" / asset_id / f"{asset_id}.glb"

        ok, msg = run_blender_placeholder_export(spec_json_path=spec_path, output_glb_path=out_glb)
        if ok:
            return [msg], []
        return [], [f"Mesh export failed: {msg}"]
