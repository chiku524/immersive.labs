# JSON schema spec (draft v0.1)

Canonical field meanings for tooling and LLM output. TypeScript mirrors live in `@immersive/studio-types`.

**Machine-readable schema:** [`packages/studio-types/schema/studio-asset-spec-v0.1.schema.json`](../../packages/studio-types/schema/studio-asset-spec-v0.1.schema.json) (job manifest draft: [`studio-job-manifest-v0.1.schema.json`](../../packages/studio-types/schema/studio-job-manifest-v0.1.schema.json)).

## `StudioAssetSpec`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `spec_version` | string | yes | Must be `"0.1"`. |
| `asset_id` | string | yes | Stable slug, e.g. `prop_crate_wood_01`. |
| `display_name` | string | yes | Human label for editors. |
| `category` | enum | yes | `prop` \| `environment_piece` \| `character_base` \| `material_library`. |
| `style_preset` | enum | yes | `realistic_hd_pbr` \| `anime_stylized` \| `toon_bold`. |
| `poly_budget_tris` | number | yes | Upper bound target; validator enforces preset-specific max. |
| `target_height_m` | number | no | World height in meters (Unity: 1 unit = 1 m). |
| `palette` | string[] | no | Hex colors `#RRGGBB` for style locking. |
| `tags` | string[] | yes | Search/filter tags. |
| `material_slots` | object[] | yes | See `StudioMaterialSlot` below. |
| `variants` | object[] | yes | At least one variant; each can carry `seed`. |
| `generation` | object | yes | Prompts and references. |
| `generation.source_prompt` | string | yes | User-facing description compiled by LLM or edited. |
| `generation.negative_prompt` | string | no | Preset defaults may merge with this. |
| `generation.reference_assets` | string[] | no | Paths or content hashes for style refs. |
| `unity` | object | yes | Import hints. |
| `unity.import_subfolder` | string | yes | Under the pack root, e.g. `Props/Crates`. |
| `unity.collider` | enum | yes | `box` \| `capsule` \| `mesh_convex` \| `none`. |

### `StudioMaterialSlot`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | e.g. `main`, `trim`. |
| `role` | enum | yes | `albedo` \| `normal` \| `orm` \| `emissive` \| `mask`. |
| `resolution_hint` | enum | yes | `512` \| `1024` \| `2048` \| `4096`. |
| `notes` | string | no | e.g. “trim sheet UV island 2”. |

### `StudioAssetVariant`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `variant_id` | string | yes | e.g. `damaged`, `pristine`. |
| `label` | string | yes | Editor display. |
| `seed` | number | no | Reproducibility for stochastic stages. |

## `StudioJobManifest`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `manifest_version` | string | yes | `"0.1"`. |
| `job_id` | string | yes | UUID or ULID. |
| `created_at` | string | yes | ISO-8601 UTC. |
| `engine_target` | enum | yes | `unity` (others later). |
| `assets` | object[] | yes | List of `StudioAssetSpec`. |
| `toolchain` | object | yes | Audit trail. |
| `toolchain.llm_model` | string | no | e.g. `ollama:modelname`. |
| `toolchain.image_pipeline` | string | no | e.g. `comfyui:graph@sha`. |
| `toolchain.mesh_pipeline` | string | no | e.g. `blender:4.2:script@sha`. |

## JSON Schema fragment (informative)

A formal `json-schema` file may be added under `packages/studio-types/schema/` in a later PR. Until then, treat this document and `packages/studio-types/src/index.ts` as the contract.

## Validator rules (to implement)

- `poly_budget_tris` ≤ preset maximum (define table in worker config).  
- `material_slots` must include required roles per `style_preset` (define table in [art-style-presets.md](./art-style-presets.md) appendix when implementing).  
- `asset_id` matches `^[a-z0-9_]+$`.  
- `unity.import_subfolder` no `..` path segments.
