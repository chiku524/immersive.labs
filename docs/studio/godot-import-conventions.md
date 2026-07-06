# Godot 4 import conventions (Immersive Labs studio packs)

Studio packs ship as a **folder** (or zip):

```
Models/<asset_id>/<asset_id>.glb
Textures/<asset_id>/{variant}_{slot}_{role}.png
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

1. ComfyUI writes sidecar PNGs under `Textures/<asset_id>/`.
2. Tripo or Blender writes `Models/<asset_id>/<asset_id>.glb`.
3. When both mesh and textures succeed, the worker runs `blender/bind_pbr_textures.py` to **embed** PNGs into the GLB (requires Blender on the worker).

If Blender is unavailable, use the Godot helper in your game project or wire materials manually.

## ShipHappens helper

`scripts/assets/immersive_studio_material.gd` maps known assets to sidecar PNG paths and applies `shaders/immersive_studio_orm.gdshader` (packed ORM + albedo).

```gdscript
var inst := MODEL_WELCOME.instantiate()
ImmersiveStudioMaterial.apply_to_node(inst, "env_blue_yellow_welcome_sign_01")
```

Add new entries to `ASSET_TEXTURES` when importing packs.

## Recommended Godot import settings

- **GLB**: Scene import, generate tangents, no external material override.
- **PNG**: VRAM Compressed, mipmaps on, sRGB for albedo, **non-sRGB** for ORM/normal.

## Toon tuning

For cartoon titles, keep `metallic_scale` ≤ 0.25 and `roughness_scale` ≥ 0.8 in the ORM shader. Add `emission_energy` on light-fixture assets.
