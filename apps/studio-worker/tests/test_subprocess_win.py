"""Tests for Windows silent subprocess helpers."""

from __future__ import annotations

import subprocess
import sys

import pytest

import studio_worker.subprocess_win as subprocess_win
from studio_worker.subprocess_win import apply_silent_subprocess_defaults, subprocess_no_window_kwargs


def test_subprocess_no_window_kwargs_empty_off_windows() -> None:
    if sys.platform == "win32":
        pytest.skip("platform-specific")
    assert subprocess_no_window_kwargs() == {}


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_apply_silent_subprocess_defaults_subclasses_popen() -> None:
    subprocess_win._PATCHED = False
    apply_silent_subprocess_defaults()
    assert isinstance(subprocess.Popen, type)
    assert subprocess.Popen.__name__ == "SilentPopen"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_apply_silent_subprocess_defaults_merges_creationflags(monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess_win._PATCHED = False
    seen: dict[str, object] = {}

    class RecordingPopen:
        def __init__(self, *_args, **kwargs):
            seen.update(kwargs)
            raise OSError("stop")

    monkeypatch.setattr(subprocess_win.subprocess, "Popen", RecordingPopen)
    apply_silent_subprocess_defaults()
    with pytest.raises(OSError, match="stop"):
        subprocess.Popen(["cmd"])  # type: ignore[call-arg]
    flags = int(seen.get("creationflags", 0))
    assert flags & int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
