# Production: split API and queue worker

By default the Docker image sets **`STUDIO_EMBEDDED_QUEUE_WORKER=1`**, so the FastAPI process runs a background thread that executes **`run_worker_loop`** against SQLite. That is simple for a single container but means **long Ollama / Comfy / Blender work shares the same process** that serves **`/api/studio/health`**, **`/dashboard`**, and tunnel keep-alives — a common contributor to **502 HTML** from the origin under load.

## Recommended split (one VM, two containers)

1. **API container** — `immersive-studio serve` with **`STUDIO_EMBEDDED_QUEUE_WORKER=0`** (and the same `STUDIO_REPO_ROOT` / volume as today).
2. **Queue container** — same image and volume, command **`immersive-studio queue-worker --worker-id prod-1`** (add more replicas with distinct `--worker-id` if you need parallelism and SQLite locking allows one claimer at a time per DB; for true parallelism use Postgres/Redis queue backends).

Both processes must see the **same** `queue.sqlite` and job output directory (shared volume or bind mount).

## Local compose

See **`apps/studio-worker/docker-compose.yml`** for an example **`studio-queue-worker`** service alongside **`studio-worker`** with the embedded consumer disabled on the API service.

## Rollout

1. Deploy the queue worker container and confirm logs show claims / completions.
2. Flip **`STUDIO_EMBEDDED_QUEUE_WORKER=0`** on the API service and restart API only.
3. Watch **`GET /api/studio/metrics`** (`slo.pending_oldest_age_seconds`, `slo.running_oldest_age_seconds`) while running a job.
