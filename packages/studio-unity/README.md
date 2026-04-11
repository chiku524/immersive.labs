# Immersive Studio Import (Unity)

UPM-style package for importing **Video Game Generation Studio** output folders into a Unity project. End-user pipeline overview: **`/docs`** on the marketing site (`apps/web`).

## Install

1. Open **Window → Package Manager → Add package from disk…** (or add via `Packages/manifest.json` git URL if you publish this path).
2. Select this folder (`packages/studio-unity` in the monorepo), or copy it under your Unity project as `Packages/com.immersivelabs.studio`.

## Requirements

- **Unity 2022.3 LTS** or newer (tested layout targets **URP**).
- Project should include the **Universal RP** package so `Universal Render Pipeline/Lit` resolves. If missing, the importer falls back to the Built-in **Standard** shader.
- When an `_orm` texture exists, materials prefer the hand-written URP shader **`ImmersiveStudio/Packed ORM Lit`** (`Shaders/ImmersiveStudioPackedORMLit.shader`): **R = ambient occlusion**, **G = roughness**, **B = metallic** (linear, non–Shader Graph). If that shader is missing, the importer falls back to URP Lit with a warning.

## Usage

1. Generate a pack with the Python worker (`immersive-studio run-job` or the `/studio` web UI).
2. In Unity: **Immersive Labs → Import Studio Pack…**
3. Choose the **pack folder** that contains `manifest.json` (not the zip — unzip first, or point at `output/jobs/job_*/`).

The importer copies `Textures/<asset_id>/*.png` into `Assets/ImmersiveStudioImports/<job_id>/…`, refreshes the Asset Database, and builds **URP Lit** materials by grouping PBR filenames. It then assigns Lit materials to **MeshRenderer** / **SkinnedMeshRenderer** on imported `.glb` / `.gltf`: if a glTF material name matches a PBR base (`{variant_id}_{slot_id}`), that slot uses the corresponding `{base}_Lit.mat`; otherwise slots are filled in **spec order** (variant × PBR slots), then the **preferred** slot (first variant × first PBR role), then any material in `Materials/`.

- Pattern: `{variant}_{slot}_albedo.png`, `{variant}_{slot}_normal.png`, `{variant}_{slot}_orm.png` (role suffix matters).
- **Albedo** → `_BaseMap` / `_MainTex`
- **Normal** → `_BumpMap` (texture type **Normal map**, `_NORMALMAP` keyword)
- **ORM** → `_PackedORMMap` on **Packed ORM Lit**; roughness drives smoothness as `1 - G`, metallic from **B**, diffuse ambient from **R** as occlusion

## Box colliders from `spec.json`

**Automatic:** On **Import Studio Pack**, if the manifest asset has `unity.collider == "box"`, each imported `.glb` / `.gltf` root receives a **BoxCollider** (same rules as below).

**Manual:**  
1. Select one or more GameObjects in the Hierarchy (typically a mesh root).  
2. **Immersive Labs → Apply Box Collider From spec.json…**  
3. Pick the worker’s `spec.json`. When `unity.collider` is `box`, a **BoxCollider** is added or updated:  
   - If a **Renderer** exists, bounds are derived from its world **Bounds** (converted to local space).  
   - Otherwise `target_height_m` (or `1`) drives a simple proportional box.  

Other collider types remain manual for now.

## Notes

- `spec.json` and `manifest.json` are left on disk for reference. When the worker exports **`Models/<asset_id>/*.glb`**, the importer copies those files next to the imported textures under `Assets/ImmersiveStudioImports/…` for Unity to import as usual.
- JsonUtility requires field names to match the JSON keys (`snake_case` as emitted by the worker).
