# Immersive Studio Import (Unreal Engine)

Editor plugin for importing **Video Game Generation Studio** output folders into Unreal Engine 5 projects — the Unreal counterpart to `packages/studio-unity`.

## Requirements

- **Unreal Engine 5.3+** (developed against 5.3–5.7 conventions)
- Enabled plugins (declared as dependencies in `.uplugin`): **Interchange**, **InterchangeImporter**, **glTFExporter**
- A studio pack folder containing `manifest.json`, plus `Models/` and `Textures/` subfolders

## Install

1. Copy `packages/studio-unreal/ImmersiveStudio` into your UE project’s `Plugins/` folder  
   — e.g. `YourProject/Plugins/ImmersiveStudio/`
2. Open the project and allow the plugin to compile (Editor module).
3. Confirm **Edit → Plugins → Immersive Studio Import** is enabled.

Alternatively, symlink the folder from this monorepo during development.

## Usage

1. Generate a pack with the Python worker (`immersive-studio run-job`) or the `/studio` web UI.
2. Unzip `pack.zip` if needed so you have a folder with `manifest.json` at the root.
3. In Unreal: **Tools → Import Studio Pack…**
4. Select the pack folder (not an individual file).

Imported content lands under:

```text
Content/ImmersiveStudioImports/<job_id>/<asset_id>/
  Materials/<variant>_<slot>_Inst
  <mesh assets from GLB import>
```

## What the importer does

- Parses `manifest.json` (same schema as Unity).
- Imports PNG textures using PBR naming: `{variant}_{slot}_albedo|normal|orm.png`
  - Albedo → sRGB
  - Normal → normal map compression
  - ORM → linear (R=AO, G=roughness, B=metallic — same as Unity packed ORM)
- Creates **material instances** from plugin master materials:
  - `M_StudioPackedORM` when ORM is present
  - `M_StudioBase` for albedo (+ optional normal) only
- Imports `.glb` / `.gltf` from `Models/<asset_id>/` and assigns materials to mesh slots (name match, then spec order, then preferred variant/slot).
- When `unity.collider` is `box`, adds a simple **box collision** primitive sized to mesh bounds (same hint field as Unity until a dedicated `unreal` block exists in the spec).

## Pack layout

See [docs/studio/unreal-import-conventions.md](../../docs/studio/unreal-import-conventions.md) and [unity-export-conventions.md](../../docs/studio/unity-export-conventions.md) (shared on-disk layout).

## Limitations (v0.1)

- No automated toon/anime shader graphs yet — stylized presets import as default Lit PBR.
- glTF import depends on Unreal’s Interchange/glTF stack; if import fails, check those plugins and re-import manually from Content Browser.
- `engine_target` in `manifest.json` is set by the worker (`unity` or `unreal`) when you choose the import target in `/studio` or pass `--engine-target` on the CLI.

## Related packages

| Package | Role |
|---------|------|
| `packages/studio-unity` | Unity URP one-click import |
| `packages/studio-types` | Shared manifest / spec types |
| `apps/studio-worker` | Pack generator |
