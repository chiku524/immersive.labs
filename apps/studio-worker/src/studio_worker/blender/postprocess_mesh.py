"""
Headless Blender post-process for AI-generated meshes (e.g. Tripo GLB).

Makes a generated mesh game-ready without hand-authoring geometry:
- Decimate to a triangle budget (``--target-tris``) using the Collapse modifier.
- Optionally emit a convex-hull collision mesh (``--collider mesh_convex``).
- Optionally emit lower-detail LOD GLBs (``--lods 0.5,0.25``).

Usage (Blender passes args after ``--``)::

  blender --background --python postprocess_mesh.py -- \
      --input in.glb --output out.glb --target-tris 12000 \
      --collider mesh_convex --collider-output out_collider.glb --lods 0.5,0.25

The script is intentionally defensive: any per-step failure is logged to stdout and the
original mesh is preserved so the pack still ships a usable GLB.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _argv_after_dd() -> list[str]:
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    return []


def _parse_args(argv: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    it = iter(argv)
    for a in it:
        if a.startswith("--"):
            key = a[2:]
            try:
                out[key] = next(it)
            except StopIteration:
                out[key] = ""
    return out


def _mesh_objects(bpy):  # type: ignore[no-untyped-def]
    return [o for o in bpy.data.objects if o.type == "MESH"]


def _count_tris(bpy) -> int:  # type: ignore[no-untyped-def]
    import bmesh  # type: ignore[import-not-found]

    total = 0
    for obj in _mesh_objects(bpy):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        total += len(bm.faces)
        bm.free()
    return total


def _select_only(bpy, objs) -> None:  # type: ignore[no-untyped-def]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def _apply_decimate(bpy, ratio: float) -> None:  # type: ignore[no-untyped-def]
    ratio = max(0.01, min(1.0, ratio))
    for obj in _mesh_objects(bpy):
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="studio_decimate", type="DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=mod.name)


def _export_glb(bpy, path: Path, *, selection_only: bool) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=selection_only,
    )


def _build_convex_collider(bpy, out_path: Path) -> bool:  # type: ignore[no-untyped-def]
    meshes = _mesh_objects(bpy)
    if not meshes:
        return False
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.duplicate()
    dupes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not dupes:
        return False
    bpy.context.view_layer.objects.active = dupes[0]
    if len(dupes) > 1:
        bpy.ops.object.join()
    combined = bpy.context.view_layer.objects.active
    combined.name = "studio_collider"

    bpy.ops.object.select_all(action="DESELECT")
    combined.select_set(True)
    bpy.context.view_layer.objects.active = combined
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.convex_hull()
    bpy.ops.object.mode_set(mode="OBJECT")

    _select_only(bpy, [combined])
    _export_glb(bpy, out_path, selection_only=True)
    bpy.ops.object.select_all(action="DESELECT")
    combined.select_set(True)
    bpy.ops.object.delete()
    return True


def main() -> None:
    args = _parse_args(_argv_after_dd())
    in_path = Path(args.get("input", "")).resolve()
    out_path = Path(args.get("output", "")).resolve()
    if not args.get("input") or not args.get("output"):
        print("postprocess_mesh: --input and --output required", flush=True)
        sys.exit(2)
    if not in_path.is_file():
        print(f"postprocess_mesh: input not found: {in_path}", flush=True)
        sys.exit(2)

    try:
        target_tris = int(args.get("target-tris", "0") or "0")
    except ValueError:
        target_tris = 0
    collider = (args.get("collider", "") or "").strip().lower()
    collider_out = args.get("collider-output", "")
    lods_raw = (args.get("lods", "") or "").strip()

    try:
        import bpy  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover - only outside Blender
        raise SystemExit(f"postprocess_mesh must run inside Blender: {e}") from e

    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        bpy.ops.import_scene.gltf(filepath=str(in_path))
    except Exception as e:  # noqa: BLE001
        print(f"postprocess_mesh: import failed ({e})", flush=True)
        sys.exit(3)

    before = _count_tris(bpy)
    print(f"postprocess_mesh: imported tris={before}", flush=True)

    if target_tris > 0 and before > target_tris:
        ratio = target_tris / float(before)
        try:
            _apply_decimate(bpy, ratio)
            after = _count_tris(bpy)
            print(
                f"postprocess_mesh: decimated {before}->{after} tris "
                f"(target {target_tris}, ratio {ratio:.3f})",
                flush=True,
            )
        except Exception as e:  # noqa: BLE001
            print(f"postprocess_mesh: decimate failed, keeping original ({e})", flush=True)
    else:
        print(
            f"postprocess_mesh: no decimation (tris {before} <= target {target_tris or 'n/a'})",
            flush=True,
        )

    # Export main GLB (whole scene).
    bpy.ops.object.select_all(action="SELECT")
    try:
        _export_glb(bpy, out_path, selection_only=False)
        print(f"postprocess_mesh: wrote {out_path.name}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"postprocess_mesh: export failed ({e})", flush=True)
        sys.exit(4)

    # Optional convex collider.
    if collider == "mesh_convex" and collider_out:
        try:
            ok = _build_convex_collider(bpy, Path(collider_out).resolve())
            print(
                f"postprocess_mesh: collider {'written ' + Path(collider_out).name if ok else 'skipped (no mesh)'}",
                flush=True,
            )
        except Exception as e:  # noqa: BLE001
            print(f"postprocess_mesh: collider failed ({e})", flush=True)

    # Optional LODs (ratios relative to the already-decimated base).
    if lods_raw:
        try:
            ratios = [float(x) for x in lods_raw.split(",") if x.strip()]
        except ValueError:
            ratios = []
        for i, r in enumerate(ratios, start=1):
            try:
                bpy.ops.object.select_all(action="DESELECT")
                _apply_decimate(bpy, max(0.01, min(1.0, r)))
                lod_path = out_path.with_name(f"{out_path.stem}_LOD{i}.glb")
                bpy.ops.object.select_all(action="SELECT")
                _export_glb(bpy, lod_path, selection_only=False)
                print(f"postprocess_mesh: wrote {lod_path.name} (ratio {r})", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"postprocess_mesh: LOD{i} failed ({e})", flush=True)

    print("postprocess_mesh: done", flush=True)


if __name__ == "__main__":
    main()
