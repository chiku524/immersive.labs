from __future__ import annotations

import os

TRIPO_API_BASE = "https://api.tripo3d.ai/v2/openapi"


def mesh_provider_name() -> str:
    raw = os.environ.get("STUDIO_MESH_PROVIDER", "blender_placeholder").strip().lower()
    return raw or "blender_placeholder"


def tripo_api_key() -> str | None:
    key = os.environ.get("STUDIO_TRIPO_API_KEY", "").strip()
    return key or None


def tripo_model_version() -> str:
    return os.environ.get("STUDIO_TRIPO_MODEL_VERSION", "Turbo-v1.0-20250506").strip()


def tripo_poll_interval_s() -> float:
    return max(1.0, float(os.environ.get("STUDIO_TRIPO_POLL_INTERVAL_S", "3")))


def tripo_timeout_s() -> float:
    return max(30.0, float(os.environ.get("STUDIO_TRIPO_TIMEOUT_S", "600")))
