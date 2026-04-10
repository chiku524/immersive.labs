"""
Headless Blender export: procedural placeholder mesh from StudioAssetSpec.

Usage:
  blender --background --python export_mesh.py -- --spec /path/to/spec.json --output /path/to/out.glb

Blender passes arguments after `--` in sys.argv.

Mesh profiles (by spec.category):
- prop: stacked boxes + cylinder band (or two boxes only if tags include minimal_placeholder / single_stack)
- environment_piece: wide, low platform (single mesh)
- character_base: two-block silhouette as two meshes + multi-material when bases allow
- material_library: small reference cube
- default: single beveled cube

Materials: glTF material names are `{variant_id}_{slot_id}` PBR keys (see ordered_pbr_material_bases).
Multi-part meshes use consecutive bases (0, 1, …) modulo the number of unique bases.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

# Shipped under studio_worker/blender/; parent chain is …/studio_worker/blender → studio_worker → (src | site-packages).
# We need the directory that *contains* the `studio_worker` package on sys.path (…/src or …/site-packages).
_here = Path(__file__).resolve().parent
_import_root = _here.parents[1]
if _import_root.is_dir() and str(_import_root) not in sys.path:
    sys.path.insert(0, str(_import_root))

try:
    from studio_worker.pbr_keys import (
        mat_name_for_part,
        ordered_pbr_material_bases,
        primary_pbr_material_base,
    )
except ImportError as e:
    raise SystemExit(
        "export_mesh.py must run with the immersive-studio package installed "
        f"(missing studio_worker.pbr_keys: {e})"
    ) from e


def _argv_after_dd() -> list[str]:
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        return sys.argv[idx + 1 :]
    return []


def _seed_from_asset_id(asset_id: str) -> int:
    h = 0
    for c in asset_id:
        h = (h * 31 + ord(c)) & 0x7FFFFFFF
    return h if h > 0 else 1


def assign_pbr_named_material(obj, mat_base_name: str) -> None:
    """Assign a single-slot material so glTF material name matches Unity `{base}_Lit` lookup."""
    import bpy  # type: ignore[import-not-found]

    name = mat_base_name[:63] if len(mat_base_name) > 63 else mat_base_name
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    if obj.data.materials:
        obj.data.materials.clear()
    obj.data.materials.append(mat)


def _clear_scene() -> None:
    import bpy  # type: ignore[import-not-found]

    bpy.ops.wm.read_factory_settings(use_empty=True)


def _create_parent_empty(root_label: str):
    import bpy  # type: ignore[import-not-found]

    empty = bpy.data.objects.new(f"{root_label}_root", None)
    bpy.context.collection.objects.link(empty)
    return empty


def _apply_bevel(obj, width: float) -> None:
    import bpy  # type: ignore[import-not-found]

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bevel = obj.modifiers.new(name="ImmersiveBevel", type="BEVEL")
    bevel.width = max(width, 0.0001)
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = 0.785398  # ~45°
    bpy.ops.object.modifier_apply(modifier=bevel.name)


def _shade_smooth(obj) -> None:
    import bpy  # type: ignore[import-not-found]

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()


def _add_cube(name: str, loc, scale) -> object:
    import bpy  # type: ignore[import-not-found]

    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    return obj


def _add_cylinder(name: str, loc, scale) -> object:
    import bpy  # type: ignore[import-not-found]

    bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    return obj


def _add_uv_sphere(name: str, loc, scale) -> object:
    import bpy  # type: ignore[import-not-found]

    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    return obj


def _spec_tags_lower(spec: dict) -> set[str]:
    tags = spec.get("tags") or []
    out: set[str] = set()
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, str):
                out.add(t.lower())
    return out


def _finalize_mesh_parts(
    parts: list,
    bases: list[str],
    *,
    bevel_w: float,
    result_name: str,
) -> object:
    """Apply materials, bevel, shade; parent multiple parts under an Empty for multi-material GLB."""
    for i, p in enumerate(parts):
        assign_pbr_named_material(p, mat_name_for_part(bases, i))
        _apply_bevel(p, bevel_w)
        _shade_smooth(p)

    if len(parts) == 1:
        parts[0].name = result_name
        return parts[0]

    root = _create_parent_empty(result_name)
    for p in parts:
        p.parent = root
    return root


def build_scene_root(spec: dict, asset_id: str, height: float, rng: random.Random):
    """
    Returns the root object for export: either a single mesh or an Empty with mesh children
    (multi-material friendly).
    """
    category = str(spec.get("category") or "prop")
    bevel_w = max(height * 0.012, 0.001)
    bases = ordered_pbr_material_bases(spec)
    if not bases:
        bases = [primary_pbr_material_base(spec)]

    if category == "environment_piece":
        parts = [
            _add_cube(
                f"{asset_id}_env",
                (0.0, 0.0, height * 0.05),
                (height * 1.2, height * 1.2, height * 0.1),
            ),
        ]
        return _finalize_mesh_parts(
            parts,
            bases,
            bevel_w=bevel_w * 0.5,
            result_name=asset_id,
        )

    if category == "character_base":
        leg_h = height * 0.55
        torso_h = height * 0.42
        head_r = height * (0.11 + 0.02 * rng.random())
        bottom = _add_cube(
            f"{asset_id}_lower",
            (0.0, 0.0, leg_h * 0.5),
            (height * 0.22, height * 0.18, leg_h),
        )
        top = _add_cube(
            f"{asset_id}_upper",
            (0.0, 0.0, leg_h + torso_h * 0.5),
            (height * 0.35, height * 0.22, torso_h),
        )
        head_z = leg_h + torso_h + head_r * 0.95
        head = _add_uv_sphere(
            f"{asset_id}_head",
            (0.0, 0.0, head_z),
            (head_r, head_r, head_r),
        )
        return _finalize_mesh_parts(
            [bottom, top, head],
            bases,
            bevel_w=bevel_w * 0.7,
            result_name=asset_id,
        )

    if category == "material_library":
        parts = [
            _add_cube(
                f"{asset_id}_swatch",
                (0.0, 0.0, height * 0.25),
                (height * 0.25, height * 0.25, height * 0.5),
            ),
        ]
        return _finalize_mesh_parts(
            parts,
            bases,
            bevel_w=bevel_w * 0.4,
            result_name=asset_id,
        )

    if category == "prop":
        base_h = height * (0.48 + 0.04 * rng.random())
        top_h = height - base_h
        top_h = max(top_h, height * 0.15)
        base = _add_cube(
            f"{asset_id}_base",
            (0.0, 0.0, base_h * 0.5),
            (
                height * (0.42 + 0.05 * rng.random()),
                height * (0.42 + 0.05 * rng.random()),
                base_h,
            ),
        )
        tags = _spec_tags_lower(spec)
        band_r = height * (0.38 + 0.04 * rng.random())
        band_t = height * (0.028 + 0.006 * rng.random())
        band = _add_cylinder(
            f"{asset_id}_band",
            (0.0, 0.0, base_h),
            (band_r, band_r, band_t),
        )
        ox = height * (rng.random() - 0.5) * 0.12
        oy = height * (rng.random() - 0.5) * 0.12
        top = _add_cube(
            f"{asset_id}_top",
            (ox, oy, base_h + top_h * 0.5),
            (
                height * (0.36 + 0.06 * rng.random()),
                height * (0.36 + 0.06 * rng.random()),
                top_h,
            ),
        )
        parts = [base, band, top]
        if "minimal_placeholder" in tags or "single_stack" in tags:
            parts = [base, top]
        return _finalize_mesh_parts(
            parts,
            bases,
            bevel_w=bevel_w,
            result_name=asset_id,
        )

    # Fallback: single joined cube
    parts = [
        _add_cube(
            asset_id,
            (0.0, 0.0, height * 0.5),
            (height * 0.5, height * 0.5, height),
        ),
    ]
    return _finalize_mesh_parts(
        parts,
        bases,
        bevel_w=bevel_w,
        result_name=asset_id,
    )


def main() -> None:
    args = _argv_after_dd()
    spec_path = None
    output_path = None
    it = iter(args)
    for a in it:
        if a == "--spec":
            spec_path = Path(next(it))
        elif a == "--output":
            output_path = Path(next(it))

    if not spec_path or not output_path:
        print("Usage: blender --background --python export_mesh.py -- --spec SPEC.json --output OUT.glb")
        sys.exit(2)

    try:
        import bpy  # type: ignore[import-not-found]
    except ImportError as e:
        raise SystemExit("This script must run inside Blender: " + str(e)) from e

    data = json.loads(spec_path.read_text(encoding="utf-8"))
    spec = data.get("spec", data)
    asset_id = str(spec.get("asset_id") or "asset")
    height = float(spec.get("target_height_m") or 1.0)
    height = max(height, 0.05)

    rng = random.Random(_seed_from_asset_id(asset_id))

    _clear_scene()
    root = build_scene_root(spec, asset_id, height, rng)

    import bpy  # type: ignore[import-not-found]

    bpy.ops.object.select_all(action="DESELECT")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if root.type == "EMPTY":
        bpy.ops.export_scene.gltf(
            filepath=str(output_path),
            export_format="GLB",
            use_selection=False,
        )
    else:
        root.select_set(True)
        bpy.context.view_layer.objects.active = root
        bpy.ops.export_scene.gltf(
            filepath=str(output_path),
            export_format="GLB",
            use_selection=True,
        )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
