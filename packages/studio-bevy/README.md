# Immersive Studio — Bevy 0.19 helpers

Runtime helpers for importing **Immersive Labs studio packs** into Bevy **0.19** (current stable) projects.

## Pack layout (from worker)

```
Models/<asset_id>/<asset_id>.glb
Textures/<asset_id>/{variant}_{slot}_albedo|normal|orm.png
Bevy/pack_registry.rs           # auto-generated per job
BevyImportNotes.md
manifest.json
```

## Install in your project

```toml
# Cargo.toml
[dependencies]
bevy = "0.19"
immersive-studio-bevy = { path = "../path/to/immersive.labs/packages/studio-bevy" }
```

1. Copy `Models/<asset_id>/` (and textures) into your Bevy `assets/` tree at `assets/<bevy.import_subfolder>/<asset_id>/` (default subfolder: `models`).
2. Copy the pack's `Bevy/pack_registry.rs` into your crate (or `include!` it).
3. Register and spawn:

```rust
use bevy::prelude::*;
use immersive_studio_bevy::{spawn_prop, AssetRegistry};

fn setup(mut commands: Commands, asset_server: Res<AssetServer>) {
    let mut registry = AssetRegistry::default();
    // From Bevy/pack_registry.rs
    pack_registry::register_all(&mut registry);

    spawn_prop(
        &mut commands,
        &asset_server,
        &registry,
        "env_freight_deck_panel_01",
    );

    commands.insert_resource(registry);
}
```

## Sidecar PBR

When the GLB has no embedded textures (Comfy-only or bind step skipped):

```rust
use immersive_studio_bevy::{
    build_orm_standard_material, collect_mesh_material_entities, set_orm_material_on_entities,
};

let mat = materials.add(build_orm_standard_material(
    &asset_server,
    "models/my_prop",
    "default",
    "main",
));
let entities = collect_mesh_material_entities(root, &children, &mesh_mats);
set_orm_material_on_entities(&mut commands, &entities, mat);
```

ORM packing: R=AO, G=roughness, B=metallic (matches glTF metallicRoughness G/B; AO on the occlusion slot).

## Collision

Studio packs may include `{asset_id}_collider.glb` for `convex` colliders. Wire collision with your physics plugin (Avian, Rapier, etc.) using `bevy.collider` from the asset spec (`box` / `capsule` / `convex` / `none`).

## Units

1 Bevy unit = **1 meter** (same studio convention as Unity).

See `docs/studio/bevy-import-conventions.md` in the immersive.labs repo.
