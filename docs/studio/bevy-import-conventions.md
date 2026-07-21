# Bevy 0.19 import conventions (Immersive Labs studio packs)

Studio packs ship as a **folder** (or zip):

```
Models/<asset_id>/<asset_id>.glb
Textures/<asset_id>/{variant}_{slot}_{role}.png
Bevy/pack_registry.rs
BevyImportNotes.md
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

If Blender is unavailable, use the Bevy helpers in `packages/studio-bevy` or wire `StandardMaterial` manually.

## Bevy helpers (`packages/studio-bevy`)

Target **Bevy 0.19** (current stable). Add a path dependency, copy pack assets under `assets/`, then:

```rust
use immersive_studio_bevy::{spawn_prop, AssetRegistry};

let mut registry = AssetRegistry::default();
pack_registry::register_all(&mut registry); // from Bevy/pack_registry.rs
spawn_prop(&mut commands, &asset_server, &registry, "env_blue_yellow_welcome_sign_01");
```

glTF scenes spawn via Bevy 0.19 `WorldAssetRoot` + `#Scene0` (not the older `SceneRoot` API).

For sidecar-only packs (no embedded GLB materials):

```rust
let mat = materials.add(build_orm_standard_material(
    &asset_server, "models/my_prop", "default", "main",
));
let entities = collect_mesh_material_entities(root, &children, &mesh_mats);
set_orm_material_on_entities(&mut commands, &entities, mat);
```

## Spec block (`bevy`)

When omitted, the worker derives:

- `bevy.import_subfolder` → `models` (paths are relative to Bevy's `assets/` folder)
- `bevy.collider` from `unity.collider` (`box`, `capsule`, `convex`, `none`)

Set `engine_target: bevy` on jobs to mark Bevy as the primary import target in `manifest.json` and `README.txt`.

## Recommended import settings

- **GLB**: Keep embedded materials when Tripo/bind succeeded; otherwise apply sidecars via `build_orm_standard_material`.
- **PNG**: Albedo as sRGB; ORM and normal as linear (helpers set `ImageLoaderSettings.is_srgb` accordingly).
- **Units**: 1 unit = 1 meter.
- **Collision**: Use your physics plugin; for `convex`, prefer `{asset_id}_collider.glb` when present.

## Toon tuning

For cartoon titles, prefer lower metallic / higher roughness when authoring sidecars or overriding `StandardMaterial` factors after load.
