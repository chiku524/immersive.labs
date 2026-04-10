from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from studio_worker.paths import blender_export_script_path


def resolve_blender_executable() -> str | None:
    """
    Resolve the Blender CLI: STUDIO_BLENDER_BIN, PATH (blender / blender.exe),
    then common install locations on Windows and macOS.
    """
    override = os.environ.get("STUDIO_BLENDER_BIN", "").strip()
    if override:
        p = Path(override)
        if p.is_file():
            return str(p)
        w = shutil.which(override)
        if w:
            return w
        return override

    for name in ("blender", "blender.exe"):
        w = shutil.which(name)
        if w:
            return w

    if sys.platform == "win32":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pattern = str(Path(pf) / "Blender Foundation" / "Blender *" / "blender.exe")
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]

    if sys.platform == "darwin":
        mac = Path("/Applications/Blender.app/Contents/MacOS/Blender")
        if mac.is_file():
            return str(mac)

    return None


def blender_timeout_s() -> float:
    return max(30.0, float(os.environ.get("STUDIO_BLENDER_TIMEOUT_S", "180")))


def export_mesh_default_from_env() -> bool:
    return os.environ.get("STUDIO_EXPORT_MESH_DEFAULT", "").lower() in ("1", "true", "yes")


def run_blender_placeholder_export(
    *,
    spec_json_path: Path,
    output_glb_path: Path,
) -> tuple[bool, str]:
    """
    Run headless Blender to write a scaled placeholder cube as GLB.
    Returns (ok, message) where message is human-readable (error detail or success summary).
    """
    script = blender_export_script_path()
    if not script.is_file():
        return False, f"Blender export script missing: {script}"

    exe = resolve_blender_executable()
    if not exe:
        return (
            False,
            "Blender not found. Install Blender or set STUDIO_BLENDER_BIN to the executable path.",
        )

    output_glb_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        exe,
        "--background",
        "--python",
        str(script),
        "--",
        "--spec",
        str(spec_json_path.resolve()),
        "--output",
        str(output_glb_path.resolve()),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=blender_timeout_s(),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"Blender timed out after {blender_timeout_s():.0f}s"
    except OSError as e:
        return False, f"Could not start Blender: {e}"

    tail = (proc.stderr or proc.stdout or "")[-2000:]
    if proc.returncode != 0:
        return False, f"Blender exited {proc.returncode}: {tail.strip() or 'no output'}"

    if not output_glb_path.is_file():
        return False, f"Blender reported success but {output_glb_path.name} was not written."

    return True, f"Wrote {output_glb_path.name} ({output_glb_path.stat().st_size} bytes)"


def try_export_placeholder_for_pack(
    pack_root: Path,
    spec: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """
    Export one GLB under Models/<asset_id>/<asset_id>.glb using pack_root/spec.json.
    Returns (logs, errors) — errors are non-fatal for the overall job (listed in pack).
    """
    spec_path = pack_root / "spec.json"
    if not spec_path.is_file():
        return [], ["Mesh export skipped: spec.json not found in pack root"]

    asset_id = str(spec.get("asset_id") or "asset")
    out_glb = pack_root / "Models" / asset_id / f"{asset_id}.glb"

    ok, msg = run_blender_placeholder_export(spec_json_path=spec_path, output_glb_path=out_glb)
    if ok:
        return [msg], []
    return [], [f"Mesh export failed: {msg}"]


def apply_mesh_toolchain_to_manifest(manifest: dict[str, Any], ok: bool) -> None:
    tc = manifest.setdefault("toolchain", {})
    if ok:
        tc["mesh_pipeline"] = "blender:export_mesh.py+ok"
    else:
        tc["mesh_pipeline"] = "blender:export_mesh.py+error"
