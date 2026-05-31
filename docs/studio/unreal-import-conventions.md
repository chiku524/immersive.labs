# Unreal Engine import conventions

Studio packs use the **same on-disk layout** as Unity ([unity-export-conventions.md](./unity-export-conventions.md)). The Unreal plugin (`packages/studio-unreal`) imports that layout without a separate export step.

## Pack root layout

```text
StudioPack_<job_id>/
  manifest.json
  spec.json                     # when written by worker
  UnrealImportNotes.md          # human checklist (when written by worker)
  UnityImportNotes.md
  Models/<asset_id>/*.glb
  Textures/<asset_id>/*_{albedo|normal|orm}.png
```

## Units and orientation

- **Scale:** 1 Unreal unit = **1 centimeter** by default, while the studio spec uses **1 meter = 1 Unity unit**. glTF imports typically arrive in meters; verify scale on first import and adjust the static mesh or actor scale if needed.
- **Forward / up:** glTF is +Y up, +Z forward; Unreal is +Z up, +X forward. Unreal’s glTF importer applies axis conversion — spot-check rotation on placed actors.

## Materials

- Texture filenames follow `{variant_id}_{slot_id}_{role}.png` with `role` ∈ `albedo`, `normal`, `orm`.
- **ORM packing:** R = ambient occlusion, G = roughness, B = metallic (matches Unity `ImmersiveStudio/Packed ORM Lit`).
- Master materials live in the plugin content path `/ImmersiveStudio/Materials/` and are created on first import if missing.

## Collision

Until the asset spec gains an `unreal` block, the importer reads **`unity.collider`**:

| Value | Unreal behavior |
|-------|-----------------|
| `box` | Simple box collision on the static mesh (bounds-sized) |
| others | Not automated in v0.1 |

## Import checklist

1. Enable **Immersive Studio Import** plugin (and Interchange / glTF dependencies).
2. **Tools → Import Studio Pack…** → select folder containing `manifest.json`.
3. Review imported assets under `Content/ImmersiveStudioImports/<job_id>/`.
4. Place static meshes in a level; confirm scale and collision.
5. For marketplace/FAB polish, add LODs, thumbnails, and project-specific master materials as needed.

## Tooling

| Engine | Package | Menu |
|--------|---------|------|
| Unity | `packages/studio-unity` | Immersive Labs → Import Studio Pack… |
| Unreal | `packages/studio-unreal` | Tools → Import Studio Pack… |
