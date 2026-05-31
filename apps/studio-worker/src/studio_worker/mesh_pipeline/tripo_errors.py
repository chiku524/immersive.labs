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
    """Credit errors and missing-key hints — fall back instead of failing the job."""
    if is_tripo_credit_error(messages):
        return True
    blob = " ".join(messages).lower()
    return "studio_tripo_api_key" in blob and "requires" in blob
