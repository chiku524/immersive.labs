from __future__ import annotations

import json
import re
from typing import Any

# Tripo OpenAPI billing / quota failures (fall back to free Blender mesh).
_TRIPO_CREDIT_PATTERNS = (
    re.compile(r"enough credit", re.I),
    re.compile(r"insufficient credit", re.I),
    re.compile(r"out of credit", re.I),
    re.compile(r"purchase more credit", re.I),
    re.compile(r'"code"\s*:\s*2010'),
)


def is_tripo_credit_error(messages: list[str]) -> bool:
    """True when Tripo rejected the task for billing/quota (safe to fall back locally)."""
    blob = " ".join(messages)
    if not blob.strip():
        return False
    for pat in _TRIPO_CREDIT_PATTERNS:
        if pat.search(blob):
            return True
    try:
        if "2010" in blob:
            payload = json.loads(blob[blob.find("{") :]) if "{" in blob else {}
            if isinstance(payload, dict) and payload.get("code") == 2010:
                return True
    except (json.JSONDecodeError, ValueError):
        pass
    return False


def is_tripo_fallback_eligible_error(messages: list[str]) -> bool:
    """Tripo failures that should use Blender placeholder instead of failing the job."""
    from studio_worker.mesh_pipeline.config import mesh_fallback_enabled

    if not mesh_fallback_enabled():
        return False
    blob = " ".join(messages)
    if not blob.strip():
        return False
    blob_lower = blob.lower()
    if "banned" in blob_lower:
        return False
    if is_tripo_credit_error(messages):
        return True
    if "studio_tripo_api_key" in blob_lower and "requires" in blob_lower:
        return True
    return "tripo" in blob_lower
