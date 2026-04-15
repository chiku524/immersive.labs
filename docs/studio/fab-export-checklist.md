# Epic FAB / marketplace-oriented pack checklist

Immersive Studio emits **`manifest.json`**, **`spec.json`**, **`pack.zip`**, **`ATTRIBUTION.md`**, and **`licenses.json`**. Use this list when preparing drops for **Epic FAB** or similar storefronts (always follow Epic’s current [FAB Creator Guidelines](https://dev.epicgames.com/) and your legal counsel).

## Asset contents

- **Meshes** — GLB under `Models/<asset_id>/`; verify scale matches declared `target_height_m` / Unity import notes.  
- **Textures** — PNG under `Textures/<asset_id>/`; match PBR role filenames (`*_albedo`, `*_normal`, `*_orm`) to your materials.  
- **Unity** — The optional UPM package `com.immersivelabs.studio` imports packs into URP; confirm LTS version in `UnityImportNotes.md`.

## Metadata and compliance

- **Attribution** — Ship generated `ATTRIBUTION.md` and `licenses.json`; add engine/tool licenses (Ollama, ComfyUI checkpoints, Blender) as required by those assets.  
- **Moderation** — Worker supports env-driven blocklists (`studio_worker/moderation.py`); FAB still requires human review for IP and policy.  
- **Provenance** — Keep `generation.source_prompt` in `spec.json` for traceability; do not present AI-generated work as handcrafted without disclosure where your platform requires it.

## Technical polish

- **Collision** — `unity.collider` in the spec drives import-time primitives where implemented (`box`, etc.).  
- **Performance** — Respect `poly_budget_tris` from the spec for listing screenshots and LOD claims.  
- **ZIP layout** — `pack.zip` mirrors the on-disk Studio pack; test import in a clean Unity project before upload.

## Not covered by the generator alone

FAB often expects marketing thumbnails, video, categories, and pricing in the **publisher portal**. This repo focuses on the **technical pack**; marketing assets remain a separate step.
