from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from studio_worker.paths import blender_export_script_path
from studio_worker.subprocess_win import run_no_window


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
        # Ignore stale or wrong STUDIO_BLENDER_BIN (e.g. old image); fall through to PATH / defaults.

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

    # Linux (Docker / GCE): distro packages and common install paths
    if sys.platform.startswith("linux"):
        for p in ("/usr/bin/blender", "/usr/local/bin/blender"):
            if Path(p).is_file():
                return p

    return None


def blender_timeout_s() -> float:
    return max(30.0, float(os.environ.get("STUDIO_BLENDER_TIMEOUT_S", "180")))


def export_mesh_default_from_env() -> bool:
    from studio_worker.mesh_pipeline.config import export_mesh_default_enabled

    return export_mesh_default_enabled()


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
        proc = run_no_window(
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


def run_blender_postprocess(
    *,
    input_glb: Path,
    spec: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """
    Post-process a provider-generated GLB with headless Blender: decimate to poly budget,
    optionally emit a convex collider and LODs. Non-fatal: returns ([], []) with a skip note
    when Blender is unavailable so the pack still ships the original mesh.
    """
    from studio_worker.mesh_pipeline.config import (
        mesh_collider_export_enabled,
        mesh_lod_ratios,
        mesh_postprocess_enabled,
    )
    from studio_worker.paths import blender_postprocess_script_path

    if not mesh_postprocess_enabled():
        return [], []
    if not input_glb.is_file():
        return [], []

    script = blender_postprocess_script_path()
    if not script.is_file():
        return [f"Mesh post-process skipped: script missing ({script.name})"], []

    exe = resolve_blender_executable()
    if not exe:
        return [
            "Mesh post-process skipped: Blender not found (set STUDIO_BLENDER_BIN to decimate to poly budget)."
        ], []

    target_tris = 0
    try:
        target_tris = int(spec.get("poly_budget_tris") or 0)
    except (TypeError, ValueError):
        target_tris = 0

    collider = str((spec.get("unity") or {}).get("collider") or "").strip().lower()
    want_collider = collider == "mesh_convex" and mesh_collider_export_enabled()
    collider_out = input_glb.with_name(f"{input_glb.stem}_collider.glb") if want_collider else None
    lods = mesh_lod_ratios()

    cmd = [
        exe,
        "--background",
        "--python",
        str(script),
        "--",
        "--input",
        str(input_glb),
        "--output",
        str(input_glb),
    ]
    if target_tris > 0:
        cmd += ["--target-tris", str(target_tris)]
    if collider:
        cmd += ["--collider", collider]
    if collider_out is not None:
        cmd += ["--collider-output", str(collider_out)]
    if lods:
        cmd += ["--lods", ",".join(str(r) for r in lods)]

    try:
        proc = run_no_window(
            cmd,
            capture_output=True,
            text=True,
            timeout=blender_timeout_s(),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return [], [f"Mesh post-process timed out after {blender_timeout_s():.0f}s"]
    except OSError as e:
        return [], [f"Mesh post-process could not start Blender: {e}"]

    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    summary = [ln for ln in tail if ln.startswith("postprocess_mesh:")][-6:]
    if proc.returncode != 0:
        detail = summary[-1] if summary else (proc.stderr or "no output").strip()[:200]
        return [], [f"Mesh post-process failed (exit {proc.returncode}): {detail}"]

    logs = [f"Blender post-process: {ln.split('postprocess_mesh:', 1)[1].strip()}" for ln in summary]
    if collider_out is not None and collider_out.is_file():
        logs.append(f"Collider mesh: Models/.../{collider_out.name}")
    return (logs or ["Blender post-process: done"]), []


def try_export_placeholder_for_pack(
    pack_root: Path,
    spec: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """
    Export one GLB under Models/<asset_id>/<asset_id>.glb (legacy name; uses STUDIO_MESH_PROVIDER).
    Returns (logs, errors) — errors are non-fatal for the overall job (listed in pack).
    """
    from studio_worker.mesh_pipeline.runner import try_export_mesh_for_pack

    logs, errs, _pipeline = try_export_mesh_for_pack(pack_root, spec)
    return logs, errs


def apply_mesh_toolchain_to_manifest(
    manifest: dict[str, Any],
    ok: bool,
    *,
    pipeline_id: str = "blender:export_mesh.py",
) -> None:
    tc = manifest.setdefault("toolchain", {})
    suffix = "ok" if ok else "error"
    tc["mesh_pipeline"] = f"{pipeline_id}+{suffix}"


def run_blender_bind_pack_textures(
    *,
    pack_root: Path,
    spec: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """
    Embed sidecar Comfy PBR PNGs into the pack GLB when Blender is available.
  Non-fatal when skipped (Tripo-only packs without sidecars still ship).
    """
    from studio_worker.paths import blender_bind_textures_script_path

    asset_id = str(spec.get("asset_id") or "asset")
    glb_path = pack_root / "Models" / asset_id / f"{asset_id}.glb"
    tex_dir = pack_root / "Textures" / asset_id
    if not glb_path.is_file():
        return [], []
    if not tex_dir.is_dir() or not any(tex_dir.glob("*.png")):
        return ["Texture bind skipped: no sidecar PNGs"], []

    from studio_worker.pbr_texture_groups import diagnose_sidecar_pbr

    diag = diagnose_sidecar_pbr(spec, pack_root)
    if not diag.get("ready_for_texture_bind"):
        return [], [
            "Texture bind skipped: sidecar PNGs present but no complete albedo+ORM group after merge."
        ]

    script = blender_bind_textures_script_path()
    if not script.is_file():
        return [], [f"Texture bind skipped: script missing ({script.name})"]

    exe = resolve_blender_executable()
    if not exe:
        return [
            "Texture bind skipped: Blender not found (sidecar PNGs remain external; use engine importer or Godot helper)."
        ], []

    spec_path = pack_root / "spec.json"
    if not spec_path.is_file():
        spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

    cmd = [
        exe,
        "--background",
        "--python",
        str(script),
        "--",
        "--spec",
        str(spec_path.resolve()),
        "--pack",
        str(pack_root.resolve()),
        "--glb",
        str(glb_path.resolve()),
    ]

    try:
        proc = run_no_window(
            cmd,
            capture_output=True,
            text=True,
            timeout=blender_timeout_s(),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return [], [f"Texture bind timed out after {blender_timeout_s():.0f}s"]
    except OSError as e:
        return [], [f"Texture bind could not start Blender: {e}"]

    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    summary = [ln for ln in tail if "bind_pbr_textures:" in ln]
    if proc.returncode != 0:
        detail = summary[-1] if summary else (proc.stderr or "no output").strip()[:200]
        return [], [f"Texture bind failed (exit {proc.returncode}): {detail}"]

    logs = [ln.strip() for ln in summary] or ["bind_pbr_textures: done"]
    return logs, []
