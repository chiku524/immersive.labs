from __future__ import annotations

from pathlib import Path
from typing import Any

from studio_worker.mesh_export import resolve_blender_executable
from studio_worker.pbr_texture_groups import diagnose_sidecar_pbr


def build_pack_diagnostics(
    *,
    spec: dict[str, Any],
    pack_root: Path,
    generate_textures: bool,
    export_mesh: bool,
    mesh_pipeline: str,
    image_pipeline: str,
    texture_bind_logs: list[str],
    texture_bind_errors: list[str],
    texture_source: str = "tripo",
) -> dict[str, Any]:
    pbr = diagnose_sidecar_pbr(spec, pack_root)
    tripo_ok = "tripo" in mesh_pipeline and "+ok" in mesh_pipeline
    tripo_textured = tripo_ok and texture_source == "tripo" and generate_textures

    notes: list[str] = []
    if generate_textures and export_mesh:
        if texture_source == "tripo" and tripo_textured:
            notes.append("Tripo baked mesh + PBR textures in the GLB (STUDIO_TEXTURE_SOURCE=tripo).")
        elif texture_source == "comfy" and image_pipeline.endswith("+ok") and mesh_pipeline.endswith("+ok"):
            if texture_bind_errors:
                notes.append(
                    "Mesh and Comfy sidecar textures both succeeded, but GLB was not updated with PNGs. "
                    "Install Blender on the worker or import sidecar textures in your engine (see GodotImportNotes.md)."
                )
            elif not texture_bind_logs:
                notes.append(
                    "Mesh (Tripo) and Comfy sidecar textures are separate outputs. "
                    "Enable Blender texture-bind or set STUDIO_TEXTURE_SOURCE=tripo for Tripo PBR."
                )
            else:
                notes.append("Comfy sidecar textures were embedded into the GLB via Blender bind.")
        if pbr.get("split_slot_detected"):
            notes.append(
                "Albedo and ORM PNGs used different material slot ids; worker merged them for bind/import."
            )

    return {
        "generate_textures": generate_textures,
        "export_mesh": export_mesh,
        "texture_source": texture_source,
        "image_pipeline": image_pipeline,
        "mesh_pipeline": mesh_pipeline,
        "tripo_mesh_textured": tripo_textured,
        "blender_available": resolve_blender_executable() is not None,
        "pbr": pbr,
        "texture_bind_logs": texture_bind_logs,
        "texture_bind_errors": texture_bind_errors,
        "notes": notes,
    }
