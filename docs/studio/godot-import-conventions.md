# Godot 4 import conventions (Immersive Labs studio packs)

Studio packs ship as a **folder** (or zip):

```
Models/<asset_id>/<asset_id>.glb
Textures/<asset_id>/{variant}_{slot}_{role}.png
Godot/pack_registry.gd
GodotImportNotes.md
spec.json
manifest.json
```

## Sidecar PBR filenames

| Role   | Example filename              | Channels (ORM)        |
|--------|-------------------------------|------------------------|
| albedo | `default_main_albedo.png`     | RGB color              |
| normal | `default_main_normal.png`     | tangent-space normal   |
| orm    | `default_main_orm.png`        | R=AO, G=roughness, B=metallic |

The **material base key** is `{variant_id}_{slot_id}` (e.g. `default_main`). All roles for one surface should share the same `slot_id` (typically `main`).

## Worker pipeline

1. ComfyUI or Tripo writes textures (sidecar PNGs under `Textures/<asset_id>/`, or baked into the GLB when Tripo PBR is enabled).
2. Tripo or Blender writes `Models/<asset_id>/<asset_id>.glb`.
3. When both mesh and Comfy sidecars succeed, the worker runs `blender/bind_pbr_textures.py` to **embed** PNGs into the GLB (requires Blender on the worker).

If Blender is unavailable, use the Godot helpers in `packages/studio-godot` or wire materials manually.

## Godot helpers (`packages/studio-godot`)

Copy `scripts/` and `shaders/` into your project, then register pack assets at startup:

```gdscript
# From the pack's Godot/pack_registry.gd (auto-generated per job)
ImmersiveStudioPackRegistry.register_all()

var inst := ImmersiveStudioModel.spawn_child(parent, "env_blue_yellow_welcome_sign_01")
```

For sidecar-only packs (no embedded GLB materials):

```gdscript
ImmersiveStudioMaterial.apply_to_node(inst, asset_id, "default", {}, false)
```

Attach `immersive_studio_prop.gd` to a `Node3D` and set `asset_id` in the inspector for drop-in props.

## Spec block (`godot`)

When omitted, the worker derives:

- `godot.import_subfolder` → `assets/models`
- `godot.collider` from `unity.collider` (`box`, `capsule`, `convex`, `none`)

Set `engine_target: godot` on jobs to mark Godot as the primary import target in `manifest.json` and `README.txt`.

## Recommended Godot import settings

- **GLB**: Scene import, generate tangents, no external material override when embedded PBR succeeded.
- **PNG**: VRAM Compressed, mipmaps on, sRGB for albedo, **non-sRGB** for ORM/normal.

## Toon tuning

For cartoon titles, keep `metallic_scale` ≤ 0.25 and `roughness_scale` ≥ 0.8 in the ORM shader. Add `emission_energy` on light-fixture assets.
