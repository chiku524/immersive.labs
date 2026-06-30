from __future__ import annotations

from pathlib import Path
from typing import Any

from studio_worker.mesh_pipeline.config import mesh_provider_name
from studio_worker.mesh_pipeline.providers import (
    BlenderPlaceholderProvider,
    MeshProvider,
    TripoMeshProvider,
)
from studio_worker.mesh_pipeline.tripo_errors import is_tripo_fallback_eligible_error

_ALIASES = {
    "blender": "blender_placeholder",
    "placeholder": "blender_placeholder",
    "blender_placeholder": "blender_placeholder",
    "tripo": "tripo",
    "tripo3d": "tripo",
}

FALLBACK_PIPELINE_ID = "tripo:fallback_blender"


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


def _try_blender_fallback(
    pack_root: Path,
    spec: dict[str, Any],
    *,
    reason: str,
) -> tuple[list[str], list[str], str]:
    notice = (
        f"Tripo mesh unavailable ({reason}). "
        "Using Blender placeholder mesh as fallback — set STUDIO_TRIPO_API_KEY and keep credits "
        "at https://platform.tripo3d.ai for prompt-faithful 3D."
    )
    blender = BlenderPlaceholderProvider()
    b_logs, b_errs = blender.export_for_pack(pack_root, spec)
    logs = [notice, *b_logs]
    if b_errs:
        return logs, b_errs, FALLBACK_PIPELINE_ID
    return logs, [], FALLBACK_PIPELINE_ID


def try_export_mesh_for_pack(
    pack_root: Path,
    spec: dict[str, Any],
) -> tuple[list[str], list[str], str]:
    """
    Export mesh GLB under Models/<asset_id>/ using the configured provider.
    When STUDIO_MESH_PROVIDER=tripo (default), Tripo runs first; eligible failures fall back to Blender.
    Returns (logs, errors, pipeline_id for manifest.toolchain.mesh_pipeline).
    """
    name = _ALIASES.get(mesh_provider_name(), mesh_provider_name())

    if name == "blender_placeholder":
        provider = BlenderPlaceholderProvider()
        logs, errs = provider.export_for_pack(pack_root, spec)
        return logs, errs, provider.pipeline_id

    if name == "tripo":
        tripo = TripoMeshProvider()
        logs, errs = tripo.export_for_pack(pack_root, spec)
        if not errs:
            return logs, errs, tripo.pipeline_id
        if is_tripo_fallback_eligible_error(errs):
            reason = errs[0][:240]
            return _try_blender_fallback(pack_root, spec, reason=reason)
        return logs, errs, tripo.pipeline_id

    try:
        provider = resolve_mesh_provider()
    except ValueError as e:
        return [], [str(e)], "mesh:unknown"

    logs, errs = provider.export_for_pack(pack_root, spec)
    return logs, errs, provider.pipeline_id
