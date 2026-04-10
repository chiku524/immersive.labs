# ComfyUI integration

The worker ships **API-format workflows** (same shape as ComfyUI’s `/prompt` endpoint) under `workflows/`:

| File | Profile | Notes |
|------|---------|--------|
| `sd15_albedo_v1.api.json` | `STUDIO_COMFY_PROFILE=sd15` | 512×512, SD1.5-sized latent |
| `sdxl_albedo_v1.api.json` | `STUDIO_COMFY_PROFILE=sdxl` | 1024×1024 for SDXL checkpoints |

## Requirements

1. Run [ComfyUI](https://github.com/comfyanonymous/ComfyUI) locally (default URL `http://127.0.0.1:8188`).
2. Install a matching checkpoint into ComfyUI’s `models/checkpoints` folder.
3. Point the worker at your checkpoint name:

| Env var | Default (sd15) | Default (sdxl) |
|---------|----------------|----------------|
| `STUDIO_COMFY_URL` | `http://127.0.0.1:8188` | same |
| `STUDIO_COMFY_PROFILE` | `sd15` | set to `sdxl` |
| `STUDIO_COMFY_CHECKPOINT` | `v1-5-pruned-emaonly.ckpt` | `sd_xl_base_1.0.safetensors` |

## Generation scope (v1)

`texture_pipeline.generate_pbr_textures_for_spec` renders **one image per variant × material slot** whose `role` is `albedo`, `normal`, or `orm`, capped by `STUDIO_TEXTURE_MAX_IMAGES` (default `32`). Outputs:

`Textures/<asset_id>/<variant_id>_<slot_id>_<role>.png`

Each role uses a dedicated positive prompt (albedo vs tangent normal vs packed ORM technical). Results are **best-effort** SD outputs—inspect and re-roll in ComfyUI as needed.

## Exporting your own graphs

1. Build a graph in ComfyUI, then use **Save (API Format)**.
2. Align node IDs `1–7` with the loader / latent / CLIP / KSampler / VAE / Save stack, **or** fork `workflow_template.py` to match your IDs.
3. Keep filenames versioned: `workflow_<preset>_v2.api.json`.

## Naming convention

- `workflow_<style_preset>_v<major>.api.json` — optional per-style forks.
- Document required custom nodes and model licenses beside the JSON.
