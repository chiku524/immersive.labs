from __future__ import annotations

from pathlib import Path
from typing import Any

from studio_worker.mesh_pipeline.config import mesh_provider_name
from studio_worker.mesh_pipeline.providers import (
    BlenderPlaceholderProvider,
    MeshProvider,
    TripoMeshProvider,
)

_ALIASES = {
    "blender": "blender_placeholder",
    "placeholder": "blender_placeholder",
    "blender_placeholder": "blender_placeholder",
    "tripo": "tripo",
    "tripo3d": "tripo",
}


def resolve_mesh_provider() -> MeshProvider:
    name = _ALIASES.get(mesh_provider_name(), mesh_provider_name())
    if name == "blender_placeholder":
        return BlenderPlaceholderProvider()
    if name == "tripo":
        return TripoMeshProvider()
    raise ValueError(
        f"Unknown STUDIO_MESH_PROVIDER={mesh_provider_name()!r}. "
        "Use blender_placeholder (free, local) or tripo (needs STUDIO_TRIPO_API_KEY)."
    )


def try_export_mesh_for_pack(
    pack_root: Path,
    spec: dict[str, Any],
) -> tuple[list[str], list[str], str]:
    """
    Export mesh GLB under Models/<asset_id>/ using the configured provider.
    Returns (logs, errors, pipeline_id for manifest.toolchain.mesh_pipeline).
    """
    try:
        provider = resolve_mesh_provider()
    except ValueError as e:
        return [], [str(e)], "mesh:unknown"

    logs, errs = provider.export_for_pack(pack_root, spec)
    return logs, errs, provider.pipeline_id
