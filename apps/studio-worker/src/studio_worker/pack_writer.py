from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from studio_worker.manifest import build_job_manifest, normalize_engine_target
from studio_worker.validate import validate_asset_spec


def _unity_import_notes(
    *,
    job_id: str,
    assets: list[dict[str, Any]],
    unity_urp_hint: str,
) -> str:
    lines = [
        "# Unity import notes",
        "",
        f"- **Job ID:** `{job_id}`",
        f"- **Target pipeline:** Universal Render Pipeline (URP) — reference version: **{unity_urp_hint}**",
        "",
        "## Pack contents",
        "",
        "- `manifest.json` — full job manifest (specs + toolchain metadata).",
        "- `ATTRIBUTION.md` / `licenses.json` — tooling + checkpoint traceability (when written by worker).",
        "- `spec.json` — primary `StudioAssetSpec` for this pack (when written by worker).",
        "- `Models/` — place exported `.glb` / `.fbx` files per asset (Blender `export_mesh.py`).",
        "- `Textures/` — ComfyUI albedo outputs (`*_albedo.png`) per variant + slot.",
        "",
        "## Assets in this job",
        "",
    ]
    for a in assets:
        aid = a.get("asset_id", "?")
        st = a.get("style_preset", "?")
        unity = a.get("unity") or {}
        sub = unity.get("import_subfolder", "?")
        col = unity.get("collider", "?")
        lines.append(f"- **{aid}** — style `{st}`, import under `{sub}`, collider `{col}`")
    lines.extend(
        [
            "",
            "## Import checklist",
            "",
            "1. Create or open a **URP** project (match reference version when possible).",
            "2. Use **Immersive Labs → Import Studio Pack** (see `packages/studio-unity`) or drag this folder into `Assets/`.",
            "3. Assign **Lit** materials for PBR maps; use custom toon/anime shaders for those presets when available.",
            "4. Add colliders per `unity.collider` in the spec (box recommended for early props).",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _unreal_import_notes(
    *,
    job_id: str,
    assets: list[dict[str, Any]],
) -> str:
    lines = [
        "# Unreal Engine import notes",
        "",
        f"- **Job ID:** `{job_id}`",
        "- **Target engine:** Unreal Engine 5.3+ with the Immersive Studio Import plugin (`packages/studio-unreal`).",
        "",
        "## Pack contents",
        "",
        "- `manifest.json` — full job manifest (specs + toolchain metadata).",
        "- `Models/` — `.glb` / `.gltf` meshes per asset.",
        "- `Textures/` — PBR PNGs (`{variant}_{slot}_albedo|normal|orm.png`).",
        "",
        "## Assets in this job",
        "",
    ]
    for a in assets:
        aid = a.get("asset_id", "?")
        st = a.get("style_preset", "?")
        unity = a.get("unity") or {}
        col = unity.get("collider", "?")
        lines.append(f"- **{aid}** — style `{st}`, collider hint `{col}` (reads `unity.collider` until spec adds `unreal`).")
    lines.extend(
        [
            "",
            "## Import checklist",
            "",
            "1. Copy `packages/studio-unreal/ImmersiveStudio` into your project's `Plugins/` folder and compile.",
            "2. Enable **Interchange**, **InterchangeImporter**, and **glTFExporter** if prompted.",
            "3. **Tools → Import Studio Pack…** and select this folder (contains `manifest.json`).",
            "4. Find assets under `Content/ImmersiveStudioImports/<job_id>/`.",
            "5. Verify glTF scale (meters) vs your project's unit settings; adjust actor scale if needed.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _pack_readme(*, job_id: str, engine_target: str) -> str:
    if engine_target == "unreal":
        return (
            f"Immersive Studio pack — job `{job_id}`\n"
            "Engine target: Unreal Engine 5\n"
            "Import: UnrealImportNotes.md (Tools → Import Studio Pack… with packages/studio-unreal)\n"
        )
    return (
        f"Immersive Studio pack — job `{job_id}`\n"
        "Engine target: Unity (URP)\n"
        "Import: UnityImportNotes.md (Immersive Labs → Import Studio Pack… with packages/studio-unity)\n"
    )


def write_pack(
    output_dir: Path,
    spec: dict[str, Any],
    *,
    job_id: str | None = None,
    llm_model: str | None = None,
    image_pipeline: str | None = None,
    unity_urp_hint: str = "6000.0.x LTS (pin when smoke-tested)",
    write_spec_json: bool = False,
    engine_target: str = "unity",
) -> dict[str, Any]:
    validate_asset_spec(spec)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    target = normalize_engine_target(engine_target)

    manifest = build_job_manifest(
        [spec],
        job_id=job_id,
        llm_model=llm_model,
        image_pipeline=image_pipeline or "comfyui:unconfigured",
        mesh_pipeline="blender:export_mesh.py",
        unity_urp_version=unity_urp_hint,
        engine_target=target,
    )

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    if write_spec_json:
        (output_dir / "spec.json").write_text(
            json.dumps(spec, indent=2) + "\n", encoding="utf-8"
        )

    (output_dir / "README.txt").write_text(
        _pack_readme(job_id=manifest["job_id"], engine_target=target),
        encoding="utf-8",
    )

    if target == "unreal":
        (output_dir / "UnrealImportNotes.md").write_text(
            _unreal_import_notes(
                job_id=manifest["job_id"],
                assets=manifest["assets"],
            ),
            encoding="utf-8",
        )
    else:
        (output_dir / "UnityImportNotes.md").write_text(
            _unity_import_notes(
                job_id=manifest["job_id"],
                assets=manifest["assets"],
                unity_urp_hint=unity_urp_hint,
            ),
            encoding="utf-8",
        )

    for a in manifest["assets"]:
        aid = a["asset_id"]
        models = output_dir / "Models" / aid
        models.mkdir(parents=True, exist_ok=True)
        readme = models / "README.txt"
        readme.write_text(
            "Export placeholder: `blender --background --python <site-packages>/studio_worker/blender/export_mesh.py -- "
            f"--spec ../spec.json --output {aid}.glb`\n",
            encoding="utf-8",
        )
        tex = output_dir / "Textures" / aid
        tex.mkdir(parents=True, exist_ok=True)
        (tex / "README.txt").write_text(
            "Albedo textures land here as `{variant}_{slot}_albedo.png` when ComfyUI runs.\n",
            encoding="utf-8",
        )

    return manifest
