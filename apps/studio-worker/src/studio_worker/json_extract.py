from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
# Models that emit chain-of-thought wrappers before the JSON object.
_THINKING_BLOCKS = [
    re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE),
    re.compile(r"<thinking>[\s\S]*?</thinking>", re.IGNORECASE),
    re.compile(r"<redacted_reasoning>[\s\S]*?</redacted_reasoning>", re.IGNORECASE),
]


def _strip_thinking_wrappers(text: str) -> str:
    out = text
    for pat in _THINKING_BLOCKS:
        out = pat.sub("", out)
    return out


def _try_load_object_slice(s: str) -> dict[str, Any] | None:
    try:
        out = json.loads(s)
    except json.JSONDecodeError:
        return None
    if isinstance(out, dict):
        return out
    return None


def _extract_balanced_object(text: str) -> dict[str, Any] | None:
    """
    Find the first top-level ``{ ... }`` using brace depth, respecting JSON string rules.
    Avoids slicing from first ``{`` to last ``}`` (breaks when ``}`` appears inside a string).
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if in_string:
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start : i + 1]
                got = _try_load_object_slice(chunk)
                if got is not None:
                    return got
                return None
    return None


def _preview_for_error(text: str, limit: int = 600) -> str:
    t = text.strip().replace("\r\n", "\n")
    if len(t) <= limit:
        return t
    return t[: limit - 3] + "..."


def extract_json_object(text: str) -> dict[str, Any]:
    raw = _strip_thinking_wrappers(text).strip()
    try:
        out = json.loads(raw)
        if isinstance(out, dict):
            return out
        raise ValueError("Top-level JSON must be an object")
    except json.JSONDecodeError:
        pass

    m = _FENCE.search(raw)
    if m:
        try:
            out = json.loads(m.group(1).strip())
            if isinstance(out, dict):
                return out
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON inside fenced block: {e}") from e

    naive_start = raw.find("{")
    naive_end = raw.rfind("}")
    if naive_start != -1 and naive_end > naive_start:
        try:
            out = json.loads(raw[naive_start : naive_end + 1])
            if isinstance(out, dict):
                return out
            raise ValueError("Top-level JSON must be an object")
        except json.JSONDecodeError as e:
            balanced = _extract_balanced_object(raw)
            if balanced is not None:
                return balanced
            raise ValueError(
                f"Could not parse JSON object from model output: {e}. "
                f"First segment preview:\n{_preview_for_error(raw[naive_start : naive_end + 1])}"
            ) from e

    balanced = _extract_balanced_object(raw)
    if balanced is not None:
        return balanced

    raise ValueError(
        "No JSON object found in model output. "
        "The model must return a single JSON object (optionally inside a ```json fenced block). "
        f"Output preview:\n{_preview_for_error(raw)}"
    )
