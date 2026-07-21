# Changelog

All notable changes to the **`immersive-studio`** PyPI package and the studio worker in this monorepo are documented here. Versions follow the Python package version in `apps/studio-worker/pyproject.toml`.

## [0.1.21] — 2026-07-21

### Added

- **`engine_target: bevy`** — Bevy **0.19** pack export (`BevyImportNotes.md`, `Bevy/pack_registry.rs`, `packages/studio-bevy` helpers).
- Spec validation derives optional **`bevy`** block from `unity` import hints (`import_subfolder` default `models`, collider mapping).
- Studio UI **Import target** toggle option for Bevy 0.19.
- Bevy import guide: `docs/studio/bevy-import-conventions.md`.

### Changed

- Packs always include Bevy notes/registry alongside Unity, Unreal, and Godot.
- CLI/API `engine_target` choices: `unity` \| `unreal` \| `godot` \| `bevy`.

## [0.1.20] — 2026-07-10

### Added

- **Studio job failure panel** — classifies `last_error` (JSON / gateway / Tripo / timeout / auth) with retry + dismiss.
- **Queue transport module** — SSE with one reconnect, then polling; UI shows live stream vs polling.
- **Desktop queue-worker split** — new setups use `STUDIO_EMBEDDED_QUEUE_WORKER=0` and spawn a separate queue-worker with the API.
- **Worker version cache** — `worker-installed-version.txt` avoids spawning Python on every version read.
- **Vitest** smoke tests for failure classification helpers.

### Changed

- Stronger JSON repair (two repair rounds + non-`format:json` fallback); default SSE max duration **2h**.
- **Docker compose** defaults to split API + queue-worker (`STUDIO_EMBEDDED_QUEUE_WORKER=0`).
- **studio-edge** — no GET retries / HTML→JSON coercion on `/queue/jobs/*/events` streams.
- Desktop Vite build omits marketing/docs routes from the shell router.

### Fixed

- Windows desktop terminal flash from `python.exe -c` version checks on the health poll.

## Desktop app [0.1.13] — 2026-07-21

### Added

- **Tripo API key in Desktop Settings** — paste a `tsk_…` OpenAPI key, save to `worker.env`, and restart the API so Tripo meshes take effect immediately.
- **Tripo status pill** on the Desktop panel (configured / invalid format / missing).
- **Open env** button to edit `worker.env` (or `.env.local` in dev).

### Changed

- **Run setup** preserves an existing `STUDIO_TRIPO_API_KEY` instead of wiping it.
- Saving a Tripo key also ensures `STUDIO_MESH_PROVIDER=tripo` and related Tripo texture defaults.

## Desktop app [0.1.12] — 2026-07-10

### Fixed

- Updater `latest.json` accepts signed Windows `.exe` / `.msi` when Tauri no longer emits `*.nsis.zip` / `*.msi.zip` (v0.1.11/0.1.12 CLI behavior).

## Desktop app [0.1.11] — 2026-07-10

### Added

- Separate **queue-worker** process when `STUDIO_EMBEDDED_QUEUE_WORKER=0` (default for new setups).
- Cached installed worker version file for the Desktop panel.

### Fixed

- Flashing Windows console from periodic worker version probes.

## Desktop app [0.1.10] — 2026-07-08

### Added

- **Upgrade worker** button in the Desktop panel — `pip install -U immersive-studio` from PyPI, restarts the local API, and **preserves** `worker.env` (unlike Run setup).
- Worker version label in the Desktop panel (installed vs running API version).

### Fixed

- **Auto-update manifest** — `latest.json` now includes `windows-x86_64-nsis` (Tauri 2 primary key) plus `windows-x86_64`; CI no longer marks a release as GitHub Latest until `latest.json` is uploaded with signed bundles.

## [0.1.19] — 2026-07-07

### Changed

- **Removed category and style preset from Studio UI and API** — users submit one detailed creative brief; the worker infers category internally and pins `generation.source_prompt` to the exact user text for Tripo text-to-3D.
- CLI `generate-spec` and `run-job` no longer accept `--category` or `--style-preset`.

## Desktop app [0.1.9] — 2026-07-07

### Changed

- Studio form drops **Category** and **Style preset** dropdowns; prompts go directly to Tripo with full user detail (same web UI embedded in the desktop shell).

## [0.1.18] — 2026-07-07

### Added

- **Tripo fallback UI alert** on `/studio` when a job completes with Blender placeholder mesh instead of Tripo text-to-3D.
- **`tripo_api_key_format_valid`** worker hint — detects `tcli_…` client IDs mistakenly set as `STUDIO_TRIPO_API_KEY`.
- **`mesh_tripo_fallback_used`** in `pack_diagnostics.json` with accurate `tripo_mesh_textured` when fallback runs.

### Fixed

- Reject Tripo **client IDs** (`tcli_…`) before OpenAPI calls; require **`tsk_…` API keys**.
- **`image_pipeline`** no longer reports `tripo:baked_pbr_v1+ok` when mesh export fell back to Blender (`+fallback_blender`).

## [0.1.17] — 2026-07-07

### Fixed

- **`worker_version` in `/api/studio/health`** now reads the installed `immersive-studio` package version instead of a stale hardcoded string in `studio_worker.__init__.py`.

## [0.1.16] — 2026-07-07

### Added

- **`engine_target: godot`** — Godot 4 pack export (`GodotImportNotes.md`, `Godot/pack_registry.gd`, `packages/studio-godot` helpers).
- **`STUDIO_TEXTURE_SOURCE=tripo`** (default) — Tripo baked PBR in GLB; ComfyUI sidecars when set to `comfy`.
- **`ImmersiveStudioModel.spawn_at()`** for positioned Godot prop placement.

### Changed

- Studio UI and API accept **Godot 4** as import target alongside Unity and Unreal.
- Spec validation derives optional **`godot`** block from `unity` import hints.

## [0.1.15] — 2026-07-06

### Added

- **Blender texture bind:** `bind_pbr_textures.py` embeds Comfy sidecar PNGs into pack GLBs when mesh + textures both succeed (`texture_bind` in `manifest.toolchain`).
- **`pack_diagnostics.json`** per job explaining mesh vs sidecar texture status and bind outcome.
- **`pbr_texture_groups`:** merges split-slot albedo/ORM filenames (`*_main_albedo` + `*_orm_orm`) for bind and engine import.
- **Godot import guide:** `docs/studio/godot-import-conventions.md`.
- Desktop setup scripts auto-detect ComfyUI root and write GPU/checkpoint env lines.

### Changed

- **`STUDIO_TRIPO_TEXTURE` default is now `1`** (Tripo baked textures on); desktop `setup-desktop-studio.ps1` and local env template updated.
- PBR material slots normalize to shared slot id `main` so albedo/normal/ORM group correctly.
- Studio UI clarifies that mesh + texture toggles produce separate outputs merged by Blender bind.

## [0.1.9] — 2026-04-16

### Added

- ComfyUI polling prefers `GET /history/{prompt_id}` when supported; `STUDIO_COMFY_HISTORY_MODE=full` forces legacy full `/history` polling.
- Parallel texture generation via `STUDIO_COMFY_MAX_CONCURRENT` (default 1); texture output size from `material_slots` resolution hints with `STUDIO_TEXTURE_MAX_SIDE` and per-style `STUDIO_TEXTURE_MAX_SIDE_*` caps.
- Optional `STUDIO_JOB_TEXTURES_BEFORE_MESH` to run the Comfy texture pass before Blender mesh export.
- In-flight queue job progress: `progress_json` / `progress` on queue rows, `texture_progress.json` in the pack folder, and `/studio` UI progress during queued full jobs.
- `immersive-studio doctor` and dashboard `worker_hints` report queue backend, Postgres/Redis presence, concurrency, and texture caps.
- Docs: `docs/studio/scaling-multiprocess-queue.md`, `docs/studio/fab-export-checklist.md`.
- `scripts/studio-cloudflare-tunnel/verify-studio-local.sh` and **`verify-studio-local.ps1`** for Ollama + local FastAPI checks without **systemd** (Windows-friendly).
- **Ollama resilience:** `STUDIO_OLLAMA_CONNECT_TIMEOUT_S`, optional **`GET /api/tags`** preflight (`STUDIO_OLLAMA_PREFLIGHT`), model presence check (`STUDIO_OLLAMA_VERIFY_MODEL`), and **`STUDIO_OLLAMA_DISABLED`** to force mock specs on the server. Dashboard `worker_hints` includes `ollama_connect_timeout_s`, `ollama_preflight`, `ollama_verify_model`, `ollama_disabled`. Generate-spec **`meta`** includes `ollama_disabled`.

### Changed

- **Ollama defaults:** base read timeout when unset **600s** (was 3000), per-attempt cap **3600s** (was 14400), env read clamp **15–3600** (was 30–14400).
- `GET /api/studio/dashboard` `worker_hints` includes `comfy_max_concurrent`, `job_textures_before_mesh`, `texture_global_max_side`, `queue_backend`, `postgres_configured`, `redis_configured`, plus the new Ollama operator fields above.
- Embedded SQLite queue consumer logs a one-line hint to run a separate `queue-worker` when under load.
- **`apps/studio-edge`:** `ORIGIN_URL` is set in **`wrangler.toml`** `[vars]` for deploys that prefer config over secrets. Remove any existing **`wrangler secret`** named `ORIGIN_URL` before deploy (Cloudflare error **10053** if both exist).

### Documentation

- Refreshed **Ollama** tuning across `docs/studio/essentials.md`, `apps/studio-worker/README.md`, `apps/studio-edge/README.md`, `docs/studio/deploy-gcp-free-vm.md`, `docs/studio/security-operational-checklist.md`, `docs/studio/platform-manual.md`, `scripts/local-pc-studio/README.md`, root **`README.md`**, **`AGENTS.md`**, **`CHANGELOG.md`**, **`apps/web`** (`StudioPage`, `DocsPage`), and **`packages/studio-types`** `StudioWorkerHints` for new fields.

## [0.1.0] — 2026-04-10

### Added

- Initial PyPI publication as **`immersive-studio`**: CLI (`immersive-studio`), import package **`immersive_studio`**, and **`studio_worker`** implementation.
- Unity-oriented job packs (`manifest.json`, `spec.json`, `pack.zip`), optional ComfyUI PBR textures and Blender placeholder GLB export.
- FastAPI worker for the `/studio` web UI; GitHub Actions workflow to build and upload to PyPI with **`twine`** and repository secret **`PYPI_API_TOKEN`**.

[0.1.9]: https://pypi.org/project/immersive-studio/0.1.9/
[0.1.0]: https://pypi.org/project/immersive-studio/0.1.0/
