# Hardening (Phase 6)

Operational controls for the **Video Game Generation Studio** worker.

## Moderation

- All natural-language prompts pass through `studio_worker.moderation.assert_prompt_allowed` before LLM/mock spec generation.
- **Disable** entirely (internal lab only): `STUDIO_MODERATION_DISABLED=1`.
- **Custom blocklist (comma-separated substrings, case-insensitive):** `STUDIO_PROMPT_BLOCKLIST=foo,bar`.
- **Blocklist file (one phrase per line, `#` comments allowed):** `STUDIO_PROMPT_BLOCKLIST_FILE=/path/to/list.txt`.
- **Max prompt length:** `STUDIO_PROMPT_MAX_CHARS` (default `8000`).

## Quotas

- `STUDIO_JOBS_MAX_COUNT` — cap on rows kept in `output/jobs/index.json` (default `200`). Oldest entries are removed **and their folders deleted** when exceeded.
- `STUDIO_JOBS_MAX_TOTAL_BYTES` — soft target for total bytes under `output/jobs/` (default `5368709120` ≈ 5 GiB). `prune_oldest_jobs` deletes from the tail of the index until usage fits.
- **Disable** (not recommended): `STUDIO_QUOTAS_DISABLED=1`.
- `enforce_quota_before_new_job()` runs at the start of `run_studio_job`.

## Attribution

Every pack written by `run_studio_job`, `POST /api/studio/pack`, and `immersive-studio pack` includes:

- `ATTRIBUTION.md` — human-readable summary (checkpoint filename, workflow files, LLM label, third-party mentions).
- `licenses.json` — machine-readable snapshot (no redistribution of model weights; user must comply with checkpoint licenses).

## CI

- **PR / push:** `.github/workflows/studio-worker.yml` installs `apps/studio-worker[dev]` and runs `pytest`.
- **Blender:** `.github/workflows/studio-worker-blender.yml` downloads a **pinned** Blender Linux tarball (cached between runs) and executes a headless `export_mesh.py` smoke test.
- **GPU / Comfy:** `.github/workflows/studio-worker-gpu-comfy.yml` — **manual** `workflow_dispatch`; choose **`self-hosted`** runner plus secrets, or `ubuntu-latest` if `STUDIO_COMFY_URL` points at a reachable ComfyUI. Set `STUDIO_RUN_GPU_COMFY_TESTS=1` for local opt-in.

See [essentials.md](./essentials.md) for a consolidated workflow table.
