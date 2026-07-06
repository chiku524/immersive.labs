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
        "- `Models/` — place exported `.glb` / `.gltf` files per asset (Tripo or Blender `export_mesh.py`).",
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
        "- `Models/` — `.glb` / `.gltf` meshes per asset (Tripo text-to-3D or Blender placeholder fallback).",
        "- `Textures/` — PBR PNGs (`{variant}_{slot}_albedo|normal|orm.png`).",
        "",
        "## Assets in this job",
        "",
    ]
    for a in assets:
        aid = a.get("asset_id", "?")
        st = a.get("style_preset", "?")
        unreal = a.get("unreal") or {}
        unity = a.get("unity") or {}
        sub = unreal.get("import_subfolder") or unity.get("import_subfolder", "?")
        collision = unreal.get("collision_complexity") or _unity_collider_to_unreal(unity.get("collider"))
        lines.append(
            f"- **{aid}** — style `{st}`, import under `{sub}`, collision `{collision}` (from `unreal.collision_complexity`)."
        )
    lines.extend(
        [
            "",
            "## Import checklist",
            "",
            "1. Copy `packages/studio-unreal/ImmersiveStudio` into your project's `Plugins/` folder and compile.",
            "2. Enable **Interchange**, **InterchangeImporter**, and **glTFExporter** if prompted.",
            "3. **Tools → Import Studio Pack…** and select this folder (contains `manifest.json`).",
            "4. Find assets under `Content/ImmersiveStudioImports/<job_id>/` (spec `unreal.import_subfolder` is the intended in-project layout).",
            "5. Collision: `simple` → box body; `convex` → hull from `{asset_id}_collider.glb` baked into the static mesh body (bounds box fallback); `complex` → use-complex-as-simple; `none` → no collision.",
            "6. Verify glTF scale (meters) vs your project's unit settings; adjust actor scale if needed.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _unity_collider_to_unreal(collider: Any) -> str:
    mapping = {"box": "simple", "capsule": "simple", "mesh_convex": "convex", "none": "none"}
    if isinstance(collider, str):
        return mapping.get(collider.strip().lower(), "simple")
    return "simple"


def _unity_collider_to_godot(collider: Any) -> str:
    mapping = {"box": "box", "capsule": "capsule", "mesh_convex": "convex", "none": "none"}
    if isinstance(collider, str):
        return mapping.get(collider.strip().lower(), "box")
    return "box"


def _godot_import_notes(
    *,
    job_id: str,
    assets: list[dict[str, Any]],
) -> str:
    lines = [
        "# Godot 4 import notes",
        "",
        f"- **Job ID:** `{job_id}`",
        "- **Target engine:** Godot 4.x with Immersive Studio helpers (`packages/studio-godot`).",
        "",
        "## Pack contents",
        "",
        "- `manifest.json` — full job manifest (specs + toolchain metadata).",
        "- `Models/` — `.glb` meshes per asset (Tripo text-to-3D or Blender placeholder fallback).",
        "- `Textures/` — PBR PNGs (`{variant}_{slot}_albedo|normal|orm.png`).",
        "- `Godot/pack_registry.gd` — auto-generated registry snippet for `ImmersiveStudioMaterial.register_asset()`.",
        "",
        "## Assets in this job",
        "",
    ]
    for a in assets:
        aid = a.get("asset_id", "?")
        st = a.get("style_preset", "?")
        godot = a.get("godot") or {}
        unity = a.get("unity") or {}
        sub = godot.get("import_subfolder") or "assets/models"
        collider = godot.get("collider") or _unity_collider_to_godot(unity.get("collider"))
        height = a.get("target_height_m", "?")
        lines.append(
            f"- **{aid}** — style `{st}`, copy under `res://{sub}/{aid}/`, "
            f"collider `{collider}`, target height `{height}` m."
        )
    lines.extend(
        [
            "",
            "## Import checklist",
            "",
            "1. Copy `Models/<asset_id>/` into your Godot project at `res://<godot.import_subfolder>/<asset_id>/`.",
            "2. Copy sidecar textures from `Textures/<asset_id>/` into the same folder (when ComfyUI or bind step ran).",
            "3. Copy `packages/studio-godot/scripts/` and `shaders/` into your project (see package README).",
            "4. Copy `Godot/pack_registry.gd` into your project and call `ImmersiveStudioPackRegistry.register_all()` from an autoload or `_ready()`.",
            "5. Spawn props with `ImmersiveStudioModel.spawn_child(parent, asset_id)` or attach `immersive_studio_prop.gd` to a `Node3D`.",
            "6. Add collision per `godot.collider`: `box`/`capsule` → `CollisionShape3D`; `convex` → mesh convex hull; `none` → visual-only.",
            "7. GLB import: generate tangents; keep embedded materials when Tripo/bind succeeded, otherwise apply sidecars via `ImmersiveStudioMaterial.apply_to_node()`.",
            "",
            "Deep reference: `docs/studio/godot-import-conventions.md` in the immersive.labs repo.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_godot_pack_registry(
    output_dir: Path,
    *,
    job_id: str,
    assets: list[dict[str, Any]],
) -> None:
    godot_dir = output_dir / "Godot"
    godot_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Auto-generated by Immersive Studio — merge into your project or autoload at startup.",
        "extends RefCounted",
        "class_name ImmersiveStudioPackRegistry",
        "",
        f'const JOB_ID := "{job_id}"',
        "",
        "static func register_all() -> void:",
    ]
    if not assets:
        lines.append("\tpass")
    else:
        for a in assets:
            aid = a["asset_id"]
            godot = a.get("godot") or {}
            sub = str(godot.get("import_subfolder") or "assets/models").strip().strip("/")
            model = f"res://{sub}/{aid}/{aid}.glb"
            texture_root = f"res://{sub}/{aid}"
            height = a.get("target_height_m")
            height_arg = f"{float(height):.4g}" if isinstance(height, (int, float)) else "-1.0"
            lines.extend(
                [
                    f'\tImmersiveStudioMaterial.register_asset(',
                    f'\t\t"{aid}",',
                    f'\t\t"{model}",',
                    f"\t\t{height_arg},",
                    f"\t\t-1.0,",
                    f'\t\t"{texture_root}",',
                    f"\t)",
                ]
            )
    (godot_dir / "pack_registry.gd").write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_godot_diagnostics_notes(output_dir: Path, notes: list[str]) -> None:
    """Append pack diagnostics to GodotImportNotes.md without replacing the import guide."""
    if not notes:
        return
    path = output_dir / "GodotImportNotes.md"
    if path.is_file():
        existing = path.read_text(encoding="utf-8").rstrip()
    else:
        existing = "# Godot 4 import notes\n"
    block = "\n## Pack diagnostics\n\n" + "\n".join(f"- {line}" for line in notes)
    path.write_text(existing + block + "\n", encoding="utf-8")


def _pack_readme(*, job_id: str, engine_target: str) -> str:
    primary_by_target = {
        "unreal": "Unreal Engine 5",
        "godot": "Godot 4",
        "unity": "Unity (URP)",
    }
    notes_by_target = {
        "unreal": "UnrealImportNotes.md (Tools → Import Studio Pack… with packages/studio-unreal)",
        "godot": "GodotImportNotes.md (copy Models + Godot/pack_registry.gd; packages/studio-godot helpers)",
        "unity": "UnityImportNotes.md (Immersive Labs → Import Studio Pack… with packages/studio-unity)",
    }
    primary = primary_by_target.get(engine_target, "Unity (URP)")
    primary_notes = notes_by_target.get(engine_target, notes_by_target["unity"])
    return (
        f"Immersive Studio pack — job `{job_id}`\n"
        f"Primary engine target (manifest): {primary}\n"
        "Meshes: Models/<asset_id>/*.glb — same GLB for Unity, Unreal, and Godot (Tripo or Blender fallback)\n"
        f"Primary import guide: {primary_notes}\n"
        "Also included: UnityImportNotes.md, UnrealImportNotes.md, and GodotImportNotes.md\n"
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

    (output_dir / "UnrealImportNotes.md").write_text(
        _unreal_import_notes(
            job_id=manifest["job_id"],
            assets=manifest["assets"],
        ),
        encoding="utf-8",
    )
    (output_dir / "UnityImportNotes.md").write_text(
        _unity_import_notes(
            job_id=manifest["job_id"],
            assets=manifest["assets"],
            unity_urp_hint=unity_urp_hint,
        ),
        encoding="utf-8",
    )
    (output_dir / "GodotImportNotes.md").write_text(
        _godot_import_notes(
            job_id=manifest["job_id"],
            assets=manifest["assets"],
        ),
        encoding="utf-8",
    )
    _write_godot_pack_registry(
        output_dir,
        job_id=manifest["job_id"],
        assets=manifest["assets"],
    )

    for a in manifest["assets"]:
        aid = a["asset_id"]
        models = output_dir / "Models" / aid
        models.mkdir(parents=True, exist_ok=True)
        readme = models / "README.txt"
        readme.write_text(
            "Engine-agnostic GLB (Unity + Unreal + Godot): Tripo text_to_model or Blender placeholder fallback.\n"
            "Manual export: `blender --background --python <site-packages>/studio_worker/blender/export_mesh.py -- "
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
