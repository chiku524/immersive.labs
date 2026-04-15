# Scaling the Studio queue (API vs worker processes)

When Ollama, ComfyUI, and Blender share one small VM, long jobs can starve the HTTP API or trigger tunnel **502** responses. Use this checklist before adding hardware.

## 1. Split the queue consumer from the API

By default (`STUDIO_QUEUE_BACKEND=sqlite`), the worker may run an **embedded** consumer thread inside the FastAPI process (`STUDIO_EMBEDDED_QUEUE_WORKER` defaults on for SQLite). That is simple but ties heavy GPU/CPU work to the same process that serves `/api/studio/*`.

**Production-style setup:**

1. Start the API with **`STUDIO_EMBEDDED_QUEUE_WORKER=0`** so it only enqueues and serves status.
2. Run one or more separate processes: **`immersive-studio queue-worker --worker-id worker-a`** (or systemd units / Docker sidecars).
3. Keep **`STUDIO_QUEUE_SSE_POLL_S`** at a sensible value for `/api/studio/queue/jobs/{id}/events` (default 1s).

## 2. Redis or Postgres queue (optional)

The PyPI package supports alternate backends when you install extras and set env vars:

| Backend    | Requirements |
|-----------|---------------|
| `postgres` | `STUDIO_QUEUE_BACKEND=postgres` and `DATABASE_URL` |
| `redis`   | `STUDIO_QUEUE_BACKEND=redis` and `STUDIO_REDIS_URL` or `REDIS_URL` |
| `sqs`     | `STUDIO_QUEUE_BACKEND=sqs`, `STUDIO_SQS_QUEUE_URL`, and `DATABASE_URL` (Postgres holds rows) |

Install: `pip install 'immersive-studio[postgres]'`, `[redis]`, or `[scale]` as described in `apps/studio-worker/README.md`.

## 3. Texture throughput

- **`STUDIO_COMFY_MAX_CONCURRENT`** — number of parallel ComfyUI image requests per job (default **1**). Increase only if your Comfy host has spare VRAM; **2** is a common ceiling on a single GPU.
- **`STUDIO_COMFY_HISTORY_MODE=full`** — force legacy full `/history` polling if a proxy breaks `GET /history/{prompt_id}`.

## 4. Related docs

- `docs/studio/essentials.md` — operational reference  
- `apps/studio-edge/README.md` — Cloudflare Worker + tunnel caveats  
- `immersive-studio doctor` — prints effective queue backend, Postgres/Redis env presence, and embedded-worker mode  
