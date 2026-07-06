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
) -> dict[str, Any]:
    pbr = diagnose_sidecar_pbr(spec, pack_root)
    tripo_textured_mesh = "tripo" in mesh_pipeline and "+ok" in mesh_pipeline

    notes: list[str] = []
    if generate_textures and export_mesh:
        if image_pipeline.endswith("+ok") and mesh_pipeline.endswith("+ok"):
            if texture_bind_errors:
                notes.append(
                    "Mesh and Comfy sidecar textures both succeeded, but GLB was not updated with PNGs. "
                    "Install Blender on the worker or import sidecar textures in your engine (see GodotImportNotes.md)."
                )
            elif not texture_bind_logs:
                notes.append(
                    "Mesh (Tripo) and Comfy sidecar textures are separate outputs. "
                    "Tripo mesh is untextured unless STUDIO_TRIPO_TEXTURE=1 or Blender texture-bind runs."
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
        "image_pipeline": image_pipeline,
        "mesh_pipeline": mesh_pipeline,
        "tripo_mesh_textured": tripo_textured_mesh and "texture" in mesh_pipeline,
        "blender_available": resolve_blender_executable() is not None,
        "pbr": pbr,
        "texture_bind_logs": texture_bind_logs,
        "texture_bind_errors": texture_bind_errors,
        "notes": notes,
    }
