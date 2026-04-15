# Changelog

All notable changes to the **`immersive-studio`** PyPI package and the studio worker in this monorepo are documented here. Versions follow the Python package version in `apps/studio-worker/pyproject.toml`.

## [Unreleased]

### Added

- ComfyUI polling prefers `GET /history/{prompt_id}` when supported; `STUDIO_COMFY_HISTORY_MODE=full` forces legacy full `/history` polling.
- Parallel texture generation via `STUDIO_COMFY_MAX_CONCURRENT` (default 1); texture output size from `material_slots` resolution hints with `STUDIO_TEXTURE_MAX_SIDE` and per-style `STUDIO_TEXTURE_MAX_SIDE_*` caps.
- Optional `STUDIO_JOB_TEXTURES_BEFORE_MESH` to run the Comfy texture pass before Blender mesh export.
- In-flight queue job progress: `progress_json` / `progress` on queue rows, `texture_progress.json` in the pack folder, and `/studio` UI progress during queued full jobs.
- `immersive-studio doctor` and dashboard `worker_hints` report queue backend, Postgres/Redis presence, concurrency, and texture caps.
- Docs: `docs/studio/scaling-multiprocess-queue.md`, `docs/studio/fab-export-checklist.md`.

### Changed

- `GET /api/studio/dashboard` `worker_hints` includes `comfy_max_concurrent`, `job_textures_before_mesh`, `texture_global_max_side`, `queue_backend`, `postgres_configured`, `redis_configured`.
- Embedded SQLite queue consumer logs a one-line hint to run a separate `queue-worker` when under load.

## [0.1.0] — 2026-04-10

### Added

- Initial PyPI publication as **`immersive-studio`**: CLI (`immersive-studio`), import package **`immersive_studio`**, and **`studio_worker`** implementation.
- Unity-oriented job packs (`manifest.json`, `spec.json`, `pack.zip`), optional ComfyUI PBR textures and Blender placeholder GLB export.
- FastAPI worker for the `/studio` web UI; GitHub Actions workflow to build and upload to PyPI with **`twine`** and repository secret **`PYPI_API_TOKEN`**.

[0.1.0]: https://pypi.org/project/immersive-studio/0.1.0/
