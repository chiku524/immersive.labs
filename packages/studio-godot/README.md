# Immersive Studio — Godot 4 helpers

Runtime helpers for importing **Immersive Labs studio packs** into Godot 4.x projects.

## Pack layout (from worker)

```
Models/<asset_id>/<asset_id>.glb
Textures/<asset_id>/{variant}_{slot}_albedo|normal|orm.png
Godot/pack_registry.gd          # auto-generated per job
GodotImportNotes.md
manifest.json
```

## Install in your project

1. Copy `scripts/` and `shaders/` from this package into your Godot project (for example `res://scripts/assets/` and `res://shaders/`).
2. Import a studio pack: copy `Models/<asset_id>/` and textures into `res://assets/models/<asset_id>/` (or your `godot.import_subfolder` from the spec).
3. Copy the pack's `Godot/pack_registry.gd` and call `ImmersiveStudioPackRegistry.register_all()` once at startup (autoload or main scene `_ready()`).
4. Spawn props:

```gdscript
ImmersiveStudioModel.spawn_child(parent_node, "env_freight_deck_panel_01")
```

Or attach `immersive_studio_prop.gd` to a `Node3D` and set `asset_id` in the inspector.

## Sidecar PBR

When the GLB has no embedded textures (Comfy-only or bind step skipped), call:

```gdscript
ImmersiveStudioMaterial.apply_to_node(inst, asset_id, "default", {}, false)
```

The ORM shader expects `{variant}_{slot}_orm.png` (R=AO, G=roughness, B=metallic).

## Manual registration

```gdscript
ImmersiveStudioMaterial.register_asset(
    "my_prop",
    "res://assets/models/my_prop/my_prop.glb",
    1.0,  # target_height_m
    -1.0,
    "res://assets/models/my_prop",  # texture_root for sidecars
)
```

See `docs/studio/godot-import-conventions.md` in the immersive.labs repo for import settings and pipeline notes.
