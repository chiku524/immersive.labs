"""Windows-friendly subprocess helpers (hide console windows)."""

from __future__ import annotations

import subprocess
import sys
from typing import Any


def subprocess_no_window_kwargs() -> dict[str, Any]:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def run_no_window(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    for key, value in subprocess_no_window_kwargs().items():
        kwargs.setdefault(key, value)
    return subprocess.run(*args, **kwargs)
