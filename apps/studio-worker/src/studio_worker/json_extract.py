from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def extract_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    try:
        out = json.loads(raw)
        if isinstance(out, dict):
            return out
        raise ValueError("Top-level JSON must be an object")
    except json.JSONDecodeError:
        pass

    m = _FENCE.search(text)
    if m:
        try:
            out = json.loads(m.group(1).strip())
            if isinstance(out, dict):
                return out
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON inside fenced block: {e}") from e

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            out = json.loads(raw[start : end + 1])
            if isinstance(out, dict):
                return out
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse JSON object from model output: {e}") from e

    raise ValueError("No JSON object found in model output")
