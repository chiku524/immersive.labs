from __future__ import annotations

import pytest

from studio_worker.moderation import assert_prompt_allowed


def test_moderation_blocks_script_injection() -> None:
    with pytest.raises(ValueError):
        assert_prompt_allowed('hello <script>alert(1)</script>')


def test_moderation_allows_normal_prompt() -> None:
    assert_prompt_allowed("wooden barrel with iron rings")
