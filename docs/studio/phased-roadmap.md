# Phased roadmap

Ordered phases with **deliverables** and **risks**. Adjust durations when `apps/studio-worker` staffing and GPU profile are known.

## Phase 0 — Scope lock and monorepo foundation

**Goal:** Agree on the first vertical slice and keep the repo organized.

**Deliverables:**

- [x] Monorepo: `apps/web`, `packages/studio-types`, `docs/studio/*`.  
- [x] Written planning: vision, architecture, presets, schema draft, Unity conventions.  
- [x] Decision log: first `category` + first `style_preset` — see [DECISIONS.md](./DECISIONS.md) (`prop` + `toon_bold` first).  

**Risks:** Trying to ship all three presets at once — **mitigate** by implementing one preset end-to-end first.

---

## Phase 1 — Spec pipeline

**Goal:** Natural language → validated `StudioAssetSpec` JSON with retries and logging.

**Deliverables:**

- [x] Local LLM integration (Ollama, etc.) with **system prompt** per `style_preset`.  
- [x] JSON Schema validation (or equivalent) + business rules.  
- [x] CLI or minimal API: stdin prompt → stdout spec + exit codes.  

**Risks:** Weak JSON from local models — **mitigate** with constrained output format (e.g. JSON-only mode), repair pass, or optional hosted LLM (see [api-keys-and-local-stack.md](./api-keys-and-local-stack.md)).

---

## Phase 2 — Texture pipeline per preset

**Goal:** ComfyUI graphs that output PBR-friendly maps aligned with [art-style-presets.md](./art-style-presets.md).

**Deliverables:**

- [x] Versioned ComfyUI workflows (API JSON) in repo: `comfy/workflows/sd15_albedo_v1.api.json`, `sdxl_albedo_v1.api.json` + `comfy/README.md`.  
- [x] Mapping from `material_slots` (albedo) to `{variant}_{slot}_albedo.png` under `Textures/<asset_id>/`.  
- [ ] Smoke test matrix across two presets in CI (manual for now — requires GPU + ComfyUI).  

**Risks:** VRAM limits on 4K realistic maps — **mitigate** with resolution caps per preset.

---

## Phase 3 — Mesh pipeline v1

**Goal:** Spec + textures → exportable mesh (prefer **procedural/kitbash + Blender** first).

**Deliverables:**

- [x] Blender batch script (placeholder mesh from spec: scaled cube → `.glb`): `apps/studio-worker/blender/export_mesh.py`.  
- [x] Worker integration: optional `export_mesh` on `run-job` / enqueue / UI; writes `Models/<asset_id>/<asset_id>.glb`, updates `manifest.json` `toolchain.mesh_pipeline`, env `STUDIO_BLENDER_BIN`, `STUDIO_EXPORT_MESH_DEFAULT`, `STUDIO_BLENDER_TIMEOUT_S`.  
- [x] Unity importer copies `Models/<asset_id>/*.glb` next to imported textures.  
- [x] Unity importer assigns generated Lit materials to imported glTF mesh renderers (preferred `{variant}_{slot}_Lit`).  
- [x] Blender placeholder uses category-aware stacked/platform/column meshes + bevel; multi-part meshes assign distinct PBR material names per part when multiple `{variant}_{slot}` bases exist.  
- [x] Unity auto **box** collider on import when `unity.collider == box`.  
- [x] CI: headless Blender smoke workflow (`studio-worker-blender.yml`).  
- [ ] Optional: richer procedural kitbash / manual mesh polish (future).  

**Risks:** Text/image-to-3D quality — **mitigate** by deferring to Phase 5+ or using only as **inspiration mesh** with heavy cleanup.

---

## Phase 4 — Unity import smoke path

**Goal:** Drag-in pack works in a clean URP project.

**Deliverables:**

- [x] `UnityImportNotes.md` template filled by worker (`studio pack` command).  
- [x] Unity Editor importer package: `packages/studio-unity` (textures → URP Lit materials; collider automation still optional).  
- [x] Documented Unity URP reference in pack notes (pin exact LTS when smoke-tested).  

**Risks:** Shader mismatch across Unity versions — **mitigate** with pinned LTS and README.

---

## Phase 5 — Studio UI in `@immersive/web`

**Goal:** Non-developer-friendly job submission and download.

**Deliverables:**

- [x] Routes or section: prompt, preset, category, submit (`/studio`).  
- [x] Job list + `pack.zip` downloads via `GET /api/studio/jobs` and `GET /api/studio/jobs/{id}/download`; full job runner `POST /api/studio/jobs/run`.  

**Risks:** SSE/WebSocket complexity — **mitigate** with polling for v1.

---

## Phase 6 — Hardening

**Goal:** Production-minded quality for a **team internal** tool.

**Deliverables:**

- [x] Disk quotas + automatic pruning of oldest indexed jobs (`STUDIO_JOBS_MAX_COUNT`, `STUDIO_JOBS_MAX_TOTAL_BYTES`, `studio_worker/quotas.py`).  
- [x] License / tooling attribution per pack (`ATTRIBUTION.md`, `licenses.json` via `studio_worker/attribution.py`).  
- [x] Prompt moderation hooks (`studio_worker/moderation.py`, env-driven blocklists).  
- [x] Enqueue **idempotency_key** (per-tenant dedupe + credit-safe replay; dead jobs release the key).  
- [ ] Broader durable queue (e.g. outbox, cross-region) — future if moving beyond single-machine SQLite.  

**CI**

- [x] Default GitHub Action runs **pytest** + **respx** mocks (`.github/workflows/studio-worker.yml`).  
- [x] Optional **workflow_dispatch** stub for GPU/Comfy runners (`.github/workflows/studio-worker-gpu-comfy.yml`) + `pytest -m gpu_comfy` placeholder.  

See [hardening.md](./hardening.md).

---

## Open decisions (track in Phase 0)

1. **Worker language:** Python default for Blender; confirm team comfort.  
2. **Unity pipeline:** URP vs HDRP for reference project.  
3. **First preset:** toon vs realistic (toon often faster to validate shaders; realistic stresses texture pipeline).  

When these are decided, update [vision-and-scope.md](./vision-and-scope.md) with a one-line “Phase 0 decisions” subsection or a short `DECISIONS.md` in `docs/studio/` (optional).
