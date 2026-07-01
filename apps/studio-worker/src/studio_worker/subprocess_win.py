"""Windows-friendly subprocess helpers (hide console windows)."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

_PATCHED = False


def silent_creation_flags() -> int:
    if sys.platform != "win32":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))


def silent_startupinfo() -> subprocess.STARTUPINFO | None:
    if sys.platform != "win32":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si


def subprocess_no_window_kwargs() -> dict[str, Any]:
    if sys.platform != "win32":
        return {}
    kw: dict[str, Any] = {"creationflags": silent_creation_flags()}
    si = silent_startupinfo()
    if si is not None:
        kw["startupinfo"] = si
    return kw


def apply_silent_subprocess_defaults() -> None:
    """Patch subprocess.Popen so worker child processes hide consoles on Windows."""
    global _PATCHED
    if _PATCHED or sys.platform != "win32":
        return
    _PATCHED = True
    flags = silent_creation_flags()
    original_popen = subprocess.Popen

    class SilentPopen(original_popen):  # type: ignore[misc,valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["creationflags"] = int(kwargs.get("creationflags", 0)) | flags
            kwargs.setdefault("startupinfo", silent_startupinfo())
            super().__init__(*args, **kwargs)

    subprocess.Popen = SilentPopen  # type: ignore[assignment,misc]


def run_no_window(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    for key, value in subprocess_no_window_kwargs().items():
        kwargs.setdefault(key, value)
    return subprocess.run(*args, **kwargs)
