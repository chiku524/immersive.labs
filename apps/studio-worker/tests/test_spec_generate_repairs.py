from __future__ import annotations

from unittest.mock import patch

import pytest

from studio_worker import spec_generate


def test_extract_with_repairs_succeeds_on_second_attempt() -> None:
    def fake_chat(_system: str, _user: str, *, format_json: bool = True) -> str:
        return '{"asset_id": "crate_01", "spec_version": "0.1"}'

    with patch.object(spec_generate, "chat_completion", side_effect=fake_chat) as chat:
        out = spec_generate._extract_with_repairs("sys", "user brief", "not json at all")
    assert out["asset_id"] == "crate_01"
    assert chat.call_count == 1


def test_extract_with_repairs_falls_back_without_json_format() -> None:
    def fake_chat(_system: str, _user: str, *, format_json: bool = True) -> str:
        if format_json:
            return "still broken"
        return '{"asset_id": "ok", "spec_version": "0.1"}'

    with patch.object(spec_generate, "chat_completion", side_effect=fake_chat):
        out = spec_generate._extract_with_repairs("sys", "user", "broken")
    assert out["asset_id"] == "ok"


def test_extract_with_repairs_raises_when_all_fail() -> None:
    with patch.object(spec_generate, "chat_completion", return_value="nope"):
        with pytest.raises(ValueError, match="No JSON object"):
            spec_generate._extract_with_repairs("sys", "user", "nope")
