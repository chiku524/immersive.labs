from __future__ import annotations

import pytest

from studio_worker.cli import _doctor_comfy_dns_hint


def test_doctor_comfy_dns_hint_emits_local_override_suggestion(capsys: pytest.CaptureFixture[str]) -> None:
    _doctor_comfy_dns_hint("[Errno 11001] getaddrinfo failed")
    out = capsys.readouterr().out
    assert "127.0.0.1:8188" in out
    assert "DNS" in out


def test_doctor_comfy_dns_hint_silent_for_other_errors(capsys: pytest.CaptureFixture[str]) -> None:
    _doctor_comfy_dns_hint("connection refused")
    assert capsys.readouterr().out == ""
