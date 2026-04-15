# Video Game Generation Studio — planning

This folder captures the **planning and technical design** for the Immersive Labs **text → Unity-ready 3D assets** pipeline, hosted in this monorepo alongside the marketing site (`@immersive/web`).

## Audience

Engineers and collaborators implementing the studio worker, ComfyUI graphs, Blender automation, and Unity import tooling.

## Document map

| Document | Purpose |
|----------|---------|
| **Web (`/docs`)** | **On-site documentation hub** in `apps/web` — overview, quick start, ComfyUI, GCP + Cloudflare, Unity pointers (semantic HTML; mirrors this index for end users). |
| **[platform-manual.md](./platform-manual.md)** | **Platform hub:** table of contents, end-to-end orientation, links to every studio doc + worker README |
| **[essentials.md](./essentials.md)** | **Single reference:** env vars, **SQLite vs managed DB**, packs, Blender, Unity, CI, billing |
| **[scaling-multiprocess-queue.md](./scaling-multiprocess-queue.md)** | Split API vs `queue-worker`, Redis/Postgres queue backends, Comfy concurrency |
| **[fab-export-checklist.md](./fab-export-checklist.md)** | Epic FAB / marketplace technical checklist for generated packs |
| **[scripts/studio-cloudflare-tunnel/README.md](../../scripts/studio-cloudflare-tunnel/README.md)** | **GCE + tunnel scripts** — file table, `STUDIO_COMFY_URL` vs tunnel hostnames |
| **[releasing.md](./releasing.md)** | **PyPI releases:** version bump, schema sync, tags, GitHub Release, TestPyPI |
| [DECISIONS.md](./DECISIONS.md) | Phase 0 decisions (first preset, worker language, URP) |
| [vision-and-scope.md](./vision-and-scope.md) | Goals, non-goals, realism and style targets (anime, toon, realistic HD) |
| [architecture.md](./architecture.md) | System components, data flow, monorepo layout |
| [api-keys-and-local-stack.md](./api-keys-and-local-stack.md) | When API keys are required vs fully local operation |
| [art-style-presets.md](./art-style-presets.md) | How we achieve multiple looks without prompt-only chaos |
| [json-schema-spec.md](./json-schema-spec.md) | Canonical asset spec and job manifest (draft) |
| [unity-export-conventions.md](./unity-export-conventions.md) | Folder layout, units, materials, colliders |
| [phased-roadmap.md](./phased-roadmap.md) | Phased delivery plan with deliverables and risks |
| [hardening.md](./hardening.md) | Moderation, quotas, attribution, CI notes (Phase 6) |
| [deploy-gcp-free-vm.md](./deploy-gcp-free-vm.md) | **Free-tier GCP VM:** Docker worker, HTTPS, static host `VITE_STUDIO_API_URL` (e.g. Cloudflare Pages) |
| [cloudflare-edge-and-storage.md](./cloudflare-edge-and-storage.md) | **Workers + R2 + D1 + KV:** what fits the edge vs the Python VM, **R2 already wired** (`STUDIO_JOB_ARTIFACTS=r2`), phased migration |

## Shared types

TypeScript mirrors of the asset spec live in `@immersive/studio-types` (`packages/studio-types`). Update types and docs together when the schema evolves.

## Status

**Active implementation:** Python worker (`apps/studio-worker`) covers spec generation (Ollama + mock), JSON Schema validation, **ComfyUI albedo** workflows, persisted **jobs + zip downloads**, pack writer, and HTTP API. **`/studio`** in `@immersive/web` runs jobs and lists downloads. **Unity** import lives in `packages/studio-unity`.

See [phased-roadmap.md](./phased-roadmap.md) and [DECISIONS.md](./DECISIONS.md).

### Machine-readable schema

- [studio-asset-spec-v0.1.schema.json](../../packages/studio-types/schema/studio-asset-spec-v0.1.schema.json) (repo path: `packages/studio-types/schema/`)
