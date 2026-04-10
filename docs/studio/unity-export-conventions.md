# Unity export conventions

Conventions for packs produced by the studio worker so Unity import is boring and repeatable.

## Pack root layout

```
StudioPack_<job_id>/
  manifest.json                 # StudioJobManifest
  README.txt                    # Human summary: preset, engine version hints
  Models/
    <asset_id>/
      <variant_id>.glb          # Preferred interchange
      # or .fbx if required by pipeline
  Textures/
    <asset_id>/
      <variant_id>_<slot>_<role>.png
  Materials/                    # Optional: pre-made .mat if using Unity package
  UnityImportNotes.md           # Shader names, render pipeline (URP/HDRP/Built-in)
```

**Primary interchange:** **glTF 2.0** (`.glb`) for mesh + embedded or sidecar textures, unless a project mandates FBX.

## Units and orientation

- **Scale:** 1 Unity unit = **1 meter**. The generated mesh should import at correct world scale; manifest `target_height_m` is the cross-check.
- **Origin:** foot-on-ground for characters (future); **bottom-center** for props sitting on surfaces.
- **Forward:** document whether models face **+Z** or **+X** after export; pick one studio default and stick to it (gltf commonly +Z forward; align with Unity import settings).

## Materials and render pipeline

Document in `UnityImportNotes.md` per job:

- Target pipeline: **URP** (default assumption unless project states otherwise).  
- Base shader: Lit, or custom toon/anime shader asset path once created.  
- Texture assignments: which file maps to Base Map, Normal Map, MaskMap / Metallic/Smoothness, Emission.

Preset-specific expectations:

- **realistic_hd_pbr:** full PBR stack.  
- **anime_stylized** / **toon_bold:** may use custom shaders; albedo still exported for fallback Lit.

## Colliders

`StudioAssetSpec.unity.collider` drives post-import or bundled collider:

| Value | Unity behavior |
|-------|----------------|
| `box` | Add BoxCollider sized to mesh bounds (with configurable padding in worker). |
| `capsule` | For tall narrow props or future characters. |
| `mesh_convex` | Only when triangle count allows; watch physics cost. |
| `none` | Manual collider in scene. |

## Naming

- Files use `asset_id` and `variant_id` to avoid collisions.  
- No spaces; prefer `_` over `-` for consistency with `asset_id` regex.

## Validation checklist (automated later)

- [ ] Manifest `assets[]` length matches exported model folders.  
- [ ] Every `material_slots[].role` has a matching texture file or embedded glTF texture.  
- [ ] Triangle count ≤ `poly_budget_tris` (within tolerance if decimation is lossy).  
- [ ] Import into blank URP project without pink materials (missing shader/texture).  

## Version pinning

Record Unity **LTS version** used for smoke import in `StudioJobManifest.toolchain` extension field when we add it, or in `README.txt` until schema extends.
