from __future__ import annotations

import pytest

from studio_worker.json_extract import extract_json_object


def test_extract_plain_object() -> None:
    assert extract_json_object('{"a": 1, "b": "two"}') == {"a": 1, "b": "two"}


def test_extract_fenced_json() -> None:
    raw = """Here you go:
```json
{"ok": true}
```
"""
    assert extract_json_object(raw) == {"ok": True}


def test_extract_braces_inside_string() -> None:
    """First { to last } breaks when a string value contains }; balanced scan fixes it."""
    raw = r'Prefix {"spec_version": "0.1", "hint": "use } carefully", "n": 1} trailer'
    out = extract_json_object(raw)
    assert out["spec_version"] == "0.1"
    assert out["hint"] == "use } carefully"


def test_extract_after_thinking_block() -> None:
    raw = """<think>
reasoning here
</think>
{"x": 1}"""
    assert extract_json_object(raw) == {"x": 1}


def test_extract_redacted_reasoning_block() -> None:
    raw = """<redacted_reasoning>
plan
</redacted_reasoning>
{"asset_id": "a"}"""
    assert extract_json_object(raw) == {"asset_id": "a"}


def test_no_object_error_includes_snippet() -> None:
    with pytest.raises(ValueError, match="No JSON object"):
        extract_json_object("no braces at all just prose")


def test_top_level_array_rejected_clearly() -> None:
    with pytest.raises(ValueError, match="Top-level JSON must be an object"):
        extract_json_object("[1, 2, 3]")
