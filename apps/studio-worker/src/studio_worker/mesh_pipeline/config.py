from __future__ import annotations

import os

TRIPO_API_BASE = "https://api.tripo3d.ai/v2/openapi"


def mesh_provider_name() -> str:
    raw = os.environ.get("STUDIO_MESH_PROVIDER", "tripo").strip().lower()
    return raw or "tripo"


def mesh_fallback_enabled() -> bool:
    """When Tripo is primary, fall back to Blender placeholder on failure (default on)."""
    return _env_bool("STUDIO_MESH_FALLBACK", True)


def export_mesh_default_enabled() -> bool:
    """Run mesh export on full jobs when the client omits export_mesh."""
    raw = os.environ.get("STUDIO_EXPORT_MESH_DEFAULT")
    if raw is not None and str(raw).strip():
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    return mesh_provider_name() in ("tripo", "tripo3d")


def tripo_api_key() -> str | None:
    key = os.environ.get("STUDIO_TRIPO_API_KEY", "").strip()
    return key or None


def tripo_api_key_format_valid() -> bool:
    """Tripo OpenAPI keys start with ``tsk_``; client IDs (``tcli_``) are not valid here."""
    key = tripo_api_key()
    return bool(key) and key.startswith("tsk_")


def tripo_model_version() -> str:
    return os.environ.get("STUDIO_TRIPO_MODEL_VERSION", "Turbo-v1.0-20250506").strip()


def tripo_poll_interval_s() -> float:
    return max(1.0, float(os.environ.get("STUDIO_TRIPO_POLL_INTERVAL_S", "3")))


def tripo_timeout_s() -> float:
    return max(30.0, float(os.environ.get("STUDIO_TRIPO_TIMEOUT_S", "600")))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def texture_source() -> str:
    """Where PBR textures come from: ``tripo`` (default), ``comfy``, or ``none``."""
    raw = os.environ.get("STUDIO_TEXTURE_SOURCE", "tripo").strip().lower()
    if raw in ("tripo", "comfy", "none"):
        return raw
    return "tripo"


def tripo_texture_enabled() -> bool:
    """Tripo-baked textures cost extra credits; default on for full mesh+texture packs."""
    return _env_bool("STUDIO_TRIPO_TEXTURE", True)


def tripo_pbr_enabled() -> bool:
    if not tripo_texture_enabled():
        return False
    return _env_bool("STUDIO_TRIPO_PBR", True)


def mesh_postprocess_enabled() -> bool:
    """Run headless Blender post-processing (decimate to budget + optional collider) on generated meshes.

    Default on: only triggers on provider-generated meshes (e.g. Tripo) when Blender is available.
    """
    return _env_bool("STUDIO_MESH_POSTPROCESS", True)


def mesh_collider_export_enabled() -> bool:
    """Emit a separate convex-hull collider GLB when spec.unity.collider == mesh_convex."""
    return _env_bool("STUDIO_MESH_COLLIDER_EXPORT", True)


def mesh_lod_ratios() -> list[float]:
    """LOD decimation ratios, e.g. STUDIO_MESH_LODS='0.5,0.25'. Empty (default) = no LODs."""
    raw = os.environ.get("STUDIO_MESH_LODS", "").strip()
    if not raw:
        return []
    ratios: list[float] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            v = float(tok)
        except ValueError:
            continue
        if 0.0 < v < 1.0:
            ratios.append(v)
    return ratios
