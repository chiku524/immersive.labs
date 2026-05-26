# Scale stack: Postgres queue, R2 artifacts, local GPU worker

This guide implements **Phases A–D** from [cloudflare-edge-and-storage.md](./cloudflare-edge-and-storage.md):

| Phase | What | Where |
|-------|------|--------|
| **A** | `pack.zip` → **Cloudflare R2** | Worker uploads after each job |
| **B** | **Split API / queue** | API: `STUDIO_EMBEDDED_QUEUE_WORKER=0` |
| **C** | **Postgres** queue + tenants | Neon (recommended) or compose Postgres |
| **D** | **Queue worker fleet** | Your PC (GPU/CPU) + optional Docker worker |

**Cloudflare Worker** (`apps/studio-edge`) stays the public `api.*` hostname; **`ORIGIN_URL`** still points at the Python API (tunnel or compose).

---

## Recommended layout (local GPU is optimal)

```text
Browser → Cloudflare Worker → API (small VM or Docker) → Neon Postgres
                                    ↑
Local PC: immersive-studio queue-worker ──→ Ollama + Comfy + Blender
                                    └──→ R2 (pack.zip upload)
```

- **API host** — light: enqueue, dashboard, health (no heavy jobs in-process).
- **Your machine** — runs `queue-worker` with local Ollama/Comfy; uses the **same** `DATABASE_URL` and R2 credentials.
- **e2-micro GCP** — stop using it as the job runner; keep it only for API + tunnel if you want.

---

## 1. Accounts and cost

| Service | Purpose | Typical cost |
|---------|---------|----------------|
| **Cloudflare** | Worker, Tunnel, **R2** | Free tier + low usage; Workers Paid ~$5/mo if needed |
| **Neon** (or Supabase) | **Postgres** `DATABASE_URL` | Free tier → ~$10–25/mo |
| **Vercel** | `/studio` UI | Existing plan |
| **Your PC** | Queue worker + Ollama | $0 marginal |
| **Comfy host** | Textures (`STUDIO_COMFY_URL`) | Existing `comfy.immersivelabs.space` or local :8188 |

No Immersive-specific subscription.

---

## 2. Cloudflare R2 (Phase A)

**Automated (recommended):** create bucket `immersive-studio-packs` in the dashboard (or reuse an existing bucket), then generate `.env.scale` from Neon + Cloudflare:

```bash
export NEON_API_KEY=...
export CLOUDFLARE_API_TOKEN=...   # account token with R2 access
python scripts/studio-scale/provision-scale-env.py
```

The script sets `STUDIO_JOB_ARTIFACTS=r2`, the R2 S3 endpoint, and derives S3 keys from the Cloudflare token ([docs](https://developers.cloudflare.com/r2/api/tokens/)). Alternatively set `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` from **R2 → Manage R2 API tokens** before running the script.

After a job, `GET /api/studio/jobs/{id}/download` returns **302** to a presigned R2 URL.

---

## 3. Neon Postgres (Phase C)

1. [Neon](https://neon.tech) → New project → copy **connection string**.
2. Use **`?sslmode=require`** if not already present.
3. Set `DATABASE_URL` in `apps/studio-worker/.env.scale`.

```bash
STUDIO_QUEUE_BACKEND=postgres
STUDIO_TENANTS_BACKEND=postgres
DATABASE_URL=postgresql://user:pass@ep-....neon.tech/neondb?sslmode=require
```

Initialize tables once (from laptop or API container):

```bash
cd apps/studio-worker
pip install -e ".[scale]"
immersive-studio init-db
```

---

## 4. Config file

```bash
python scripts/studio-scale/provision-scale-env.py   # writes apps/studio-worker/.env.scale
# or: cp apps/studio-worker/.env.scale.example apps/studio-worker/.env.scale and edit
```

`.env.scale` is gitignored — do not commit secrets.

---

## 5. Run the API (Phase B) — Docker

**API only** (Neon + R2; queue worker on your PC):

```bash
npm run studio:scale:api
```

Verify:

```bash
curl -sS http://127.0.0.1:8787/api/studio/health
immersive-studio doctor --api-only   # inside container or locally with same env
```

**Optional:** Docker queue worker on the same host:

```bash
docker compose -f apps/studio-worker/docker-compose.scale.yml \
  --env-file apps/studio-worker/.env.scale \
  --profile worker up --build
```

**Optional:** bundled Postgres for experiments (`--profile local-db`):

```bash
# Use DATABASE_URL=postgresql://studio:studio@postgres:5432/studio in .env.scale
docker compose -f apps/studio-worker/docker-compose.scale.yml \
  --env-file apps/studio-worker/.env.scale \
  --profile local-db up --build
```

For a **local queue worker** against compose Postgres, publish port `5432` and set:

`DATABASE_URL=postgresql://studio:studio@127.0.0.1:5432/studio`

---

## 6. Run the queue worker on your PC (Phase D — recommended)

1. Install **Ollama** and pull a model (`tinyllama` or larger if you have RAM).
2. Point **Comfy** at your GPU box or `http://127.0.0.1:8188` if Comfy runs locally.
3. Install **Blender** on PATH (or set `STUDIO_BLENDER_BIN`) for mesh export.

```bash
# Git Bash / WSL:
bash scripts/studio-scale/run-local-queue-worker.sh

# Windows PowerShell:
.\scripts\studio-scale\run-local-queue-worker.ps1
```

Uses the same `.env.scale` as the API (`DATABASE_URL`, R2, Comfy, Ollama).

**Worker ID:** set `STUDIO_QUEUE_WORKER_ID=desktop-1` to identify rows in logs.

Run a second machine with `STUDIO_QUEUE_WORKER_ID=desktop-2` — Postgres `SKIP LOCKED` hands out different jobs.

---

## 7. Point production origin at the scale API

### Option A — GCP VM (API + tunnel only)

From your laptop (with `gcloud` and `apps/studio-worker/.env.scale`):

```bash
bash scripts/studio-scale/apply-gcp-scale-api.sh
```

This rebuilds the scale image on the VM, runs the API with `STUDIO_EMBEDDED_QUEUE_WORKER=0`, and loads env from `.env.scale`. Tunnel / Worker unchanged: `ORIGIN_URL` → `api-origin` → `127.0.0.1:8787`.

### Option B — API on your LAN + tunnel

Run `npm run studio:scale:api` locally and point `cloudflared` at `127.0.0.1:8787` (dev-style).

---

## 8. Web UI

`VITE_STUDIO_API_URL` stays your public API (`https://api.immersivelabs.space`).

Jobs are **enqueued** via the API; your **local worker** claims from Postgres and uploads zips to R2.

### Recent jobs caveat

`GET /api/studio/dashboard` → `jobs` still reads **`output/jobs/index.json` on the API host**. Completed jobs run **only on your PC** register in **that machine’s** `output/` until you add shared storage.

You still get:

- Queue status via **`GET /api/studio/queue/jobs/{id}`** (and `/studio` polling).
- **R2 download** links stored on the job result after upload.

To see packs on the API’s Recent jobs table from a local worker, either run the API locally too or share `output/` (NFS) — optional future improvement.

---

## 9. Smoke test

```bash
# 1. API health
curl -sS "$STUDIO_API_URL/api/studio/health"

# 2. Enqueue mock job
curl -sS -X POST "$STUDIO_API_URL/api/studio/queue/jobs" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"scale test","mock":true,"max_attempts":1,"idempotency_key":"scale-smoke-1"}'

# 3. Poll queue id until completed (or watch local worker logs)

# 4. Download — expect 302 to R2 when STUDIO_JOB_ARTIFACTS=r2
```

---

## 10. Troubleshooting

| Symptom | Check |
|---------|--------|
| Jobs stay `pending` | Local worker running? `DATABASE_URL` identical? `immersive-studio doctor` |
| `DATABASE_URL` errors | `pip install -e ".[scale]"`, `immersive-studio init-db` |
| R2 upload failed | Bucket, endpoint URL, token scopes; `STUDIO_JOB_ARTIFACTS=r2` |
| Comfy errors | `STUDIO_COMFY_URL` reachable from **worker** machine |
| API 502 under load | Confirm `STUDIO_EMBEDDED_QUEUE_WORKER=0` on API |

---

## See also

- [production-queue-split.md](./production-queue-split.md)
- [scaling-multiprocess-queue.md](./scaling-multiprocess-queue.md)
- [cloudflare-edge-and-storage.md](./cloudflare-edge-and-storage.md)
- [apps/studio-worker/docker-compose.scale.yml](../../apps/studio-worker/docker-compose.scale.yml)
- [scripts/studio-scale/](../../scripts/studio-scale/)
