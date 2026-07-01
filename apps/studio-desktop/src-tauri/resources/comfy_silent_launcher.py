"""Launch ComfyUI main.py without flashing console windows on Windows.

Bundled with the desktop app; also copied to scripts/local-pc-studio for manual starts.
Usage: pythonw comfy_silent_launcher.py COMFY_ROOT [--listen 127.0.0.1 --port 8188 ...]
"""

from __future__ import annotations

import os
import runpy
import subprocess
import sys

_PATCHED = False


def _apply_subprocess_patch() -> None:
    global _PATCHED
    if _PATCHED or sys.platform != "win32":
        return
    _PATCHED = True
    flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    original_popen = subprocess.Popen

    class SilentPopen(original_popen):  # type: ignore[misc,valid-type]
        def __init__(self, *args, **kwargs):
            kwargs["creationflags"] = int(kwargs.get("creationflags", 0)) | flags
            if "startupinfo" not in kwargs:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0
                kwargs["startupinfo"] = si
            super().__init__(*args, **kwargs)

    subprocess.Popen = SilentPopen  # type: ignore[assignment,misc]


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        raise SystemExit(
            "usage: pythonw comfy_silent_launcher.py COMFY_ROOT [main.py args...]"
        )

    comfy_root = os.path.abspath(argv[0])
    main_py = os.path.join(comfy_root, "main.py")
    if not os.path.isfile(main_py):
        raise SystemExit(f"main.py not found under {comfy_root}")

    _apply_subprocess_patch()
    os.chdir(comfy_root)
    sys.path.insert(0, comfy_root)
    sys.argv = [main_py, *argv[1:]]
    runpy.run_path(main_py, run_name="__main__")


if __name__ == "__main__":
    main()
