"""
Bind sidecar ComfyUI PBR PNGs into a GLB (embedded images) for engines without a pack importer.

Usage:
  blender --background --python bind_pbr_textures.py -- \\
    --spec /path/to/spec.json \\
    --pack /path/to/pack_root \\
    --glb /path/to/Models/asset_id/asset_id.glb
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
_import_root = _here.parents[1]
if _import_root.is_dir() and str(_import_root) not in sys.path:
    sys.path.insert(0, str(_import_root))

from studio_worker.pbr_texture_groups import resolve_textures_for_material_bases  # noqa: E402


def _argv_after_dd() -> list[str]:
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        return sys.argv[idx + 1 :]
    return []


def _parse_args(argv: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    i = 0
    while i < len(argv):
        key = argv[i]
        if key.startswith("--") and i + 1 < len(argv):
            out[key[2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return out


def _wire_principled_material(mat, textures: dict[str, Path]) -> None:
    import bpy  # type: ignore[import-not-found]

    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    x_tex = -500
    if "albedo" in textures:
        albedo = nodes.new("ShaderNodeTexImage")
        albedo.location = (x_tex, 200)
        albedo.image = bpy.data.images.load(str(textures["albedo"]))
        albedo.image.pack()
        links.new(albedo.outputs["Color"], bsdf.inputs["Base Color"])
        if albedo.image.depth == 32:
            links.new(albedo.outputs["Alpha"], bsdf.inputs["Alpha"])
            mat.blend_method = "BLEND"

    if "normal" in textures:
        normal_tex = nodes.new("ShaderNodeTexImage")
        normal_tex.location = (x_tex, -50)
        normal_tex.image = bpy.data.images.load(str(textures["normal"]))
        normal_tex.image.pack()
        normal_tex.image.colorspace_settings.name = "Non-Color"
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.location = (-150, -50)
        links.new(normal_tex.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

    if "orm" in textures:
        orm_tex = nodes.new("ShaderNodeTexImage")
        orm_tex.location = (x_tex, -250)
        orm_tex.image = bpy.data.images.load(str(textures["orm"]))
        orm_tex.image.pack()
        orm_tex.image.colorspace_settings.name = "Non-Color"
        sep = nodes.new("ShaderNodeSeparateColor")
        sep.location = (-250, -250)
        links.new(orm_tex.outputs["Color"], sep.inputs["Color"])
        for channel, socket_name in (
            ("Red", "Ambient Occlusion"),
            ("Green", "Roughness"),
            ("Blue", "Metallic"),
        ):
            if socket_name in bsdf.inputs:
                links.new(sep.outputs[channel], bsdf.inputs[socket_name])


def bind_textures_to_glb(*, spec: dict, pack_root: Path, glb_path: Path) -> tuple[bool, str]:
    import bpy  # type: ignore[import-not-found]

    asset_id = str(spec.get("asset_id") or "asset")
    tex_dir = pack_root / "Textures" / asset_id
    material_textures = resolve_textures_for_material_bases(spec, tex_dir)
    if not material_textures:
        return False, f"No sidecar PBR PNG groups in {tex_dir}"

    if not glb_path.is_file():
        return False, f"GLB not found: {glb_path}"

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb_path))

    default_textures = next(iter(material_textures.values()))
    rebound = 0
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            continue
        mat_textures = material_textures.get(mat.name) or default_textures
        if "albedo" not in mat_textures:
            continue
        _wire_principled_material(mat, mat_textures)
        rebound += 1

    if rebound == 0:
        return False, "No materials matched sidecar PBR groups"

    glb_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        export_image_format="AUTO",
        export_texcoords=True,
        export_materials="EXPORT",
    )
    return True, f"Bound {rebound} material(s); rewrote {glb_path.name}"


def main() -> None:
    args = _parse_args(_argv_after_dd())
    spec_path = Path(args.get("spec", ""))
    pack_root = Path(args.get("pack", ""))
    glb_path = Path(args.get("glb", ""))
    if not spec_path.is_file() or not pack_root.is_dir() or not glb_path:
        raise SystemExit("Usage: --spec <spec.json> --pack <pack_root> --glb <model.glb>")

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    ok, msg = bind_textures_to_glb(spec=spec, pack_root=pack_root, glb_path=glb_path)
    print(f"bind_pbr_textures: {msg}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
