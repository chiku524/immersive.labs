# Immersive Labs — platform manual

**One place to find how the Video Game Generation Studio fits together:** repositories, processes, configuration, APIs, scaling, billing, and links to every detailed doc in this monorepo.

**Who should read this:** operators integrating the stack in production, engineers onboarding to the codebase, and technical users who need the full picture without hunting through scattered READMEs.

---

## Table of contents

1. [What this platform is](#what-this-platform-is)
2. [Monorepo layout](#monorepo-layout)
3. [Local development (quick path)](#local-development-quick-path)
4. [Web application](#web-application) (includes **`/docs`** hub)
5. [Studio UI](#studio-ui)
6. [Python worker](#python-worker)
7. [HTTP API reference](#http-api-reference)
8. [Environment variables and pip extras](#environment-variables-and-pip-extras)
9. [Data, queues, and horizontal scale](#data-queues-and-horizontal-scale)
10. [Multi-tenant mode, API keys, and billing](#multi-tenant-mode-api-keys-and-billing)
11. [Asset pipeline](#asset-pipeline)
12. [Unity importer](#unity-importer)
13. [Schema, types, and validation](#schema-types-and-validation)
14. [Security, moderation, and hardening](#security-moderation-and-hardening)
15. [Operations: health, metrics, backups](#operations-health-metrics-backups)
16. [Deployment: Vercel, workers, and persistence](#deployment-vercel-workers-and-persistence)
17. [Testing and CI](#testing-and-ci)
18. [Full documentation index](#full-documentation-index)

---

## What this platform is

**Immersive Labs** (this monorepo) delivers a **text → Unity-ready 3D asset** workflow:

- A **web app** (`apps/web`) provides marketing pages and an interactive **Studio** at **`/studio`** (prompts, job runs, downloads).
- A **Python worker** (`apps/studio-worker`) runs LLM spec generation (Ollama or mock), **ComfyUI** texture passes, optional **Blender** placeholder mesh export, pack layout, **`pack.zip`**, job persistence, and an **HTTP API** the browser talks to.
- A **Unity UPM package** (`packages/studio-unity`) imports finished **pack folders** or zip contents into a Unity project (URP-oriented materials and conventions).

The worker and the static site are **separate deployables**: the UI does not embed SQLite or run ComfyUI; it calls a configurable **worker base URL** (see [Deployment](#16-deployment-vercel-workers-and-persistence)).

**Deeper product context:** [vision-and-scope.md](./vision-and-scope.md), [architecture.md](./architecture.md), [essentials.md](./essentials.md).

---

## Monorepo layout

| Path | Role |
|------|------|
| [`apps/web`](../../apps/web) | Vite + React — marketing site + **`/studio`** |
| [`apps/studio-worker`](../../apps/studio-worker) | Python: spec, ComfyUI, jobs, queue, HTTP API, Stripe webhooks |
| [`packages/studio-types`](../../packages/studio-types) | JSON Schema + TS types for `StudioAssetSpec` |
| [`packages/studio-unity`](../../packages/studio-unity) | Unity Editor package: import packs, PBR materials, optional colliders |
| [`docs/studio/`](./) | Studio planning + this manual |

**Root scripts:** from repo root, `npm install`, `npm run dev` — see [repository README](../../README.md).

---

## Local development (quick path)

1. **Install JS deps** (repo root): `npm install`
2. **Start the web app:** `npm run dev` → open **`http://localhost:5173/studio`**
3. **Worker (separate terminal):**
   ```bash
   cd apps/studio-worker
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -e .
   immersive-studio serve --host 127.0.0.1 --port 8787
   ```
4. **Point the UI at the worker:** set **`VITE_STUDIO_API_URL=http://127.0.0.1:8787`** in `apps/web` (e.g. `.env.development.local`) if defaults are wrong.
5. **Optional services:**
   - **Ollama** — for real LLM specs; otherwise use **mock** in the UI.
   - **ComfyUI** — for texture generation; match `STUDIO_COMFY_CHECKPOINT` to a local checkpoint ([`apps/studio-worker/comfy/README.md`](../../apps/studio-worker/comfy/README.md)).

**Async jobs:** run **`immersive-studio queue-worker --worker-id local-1`** alongside the API if you use **POST `/api/studio/queue/jobs`** instead of synchronous **`/jobs/run`**.

---

## Web application

- **Stack:** Vite + React (`@immersive/web`).
- **Studio API base URL:** **`VITE_STUDIO_API_URL`** — must match where **`immersive-studio serve`** (or production worker) is reachable. Wrong URL → health errors in `/studio`.
- **Documentation hub:** **`/docs`** — semantic, operator-oriented overview (quick start, worker, ComfyUI, Blender, GCP + Cloudflare Tunnel, Unity pointers). Source: `apps/web/src/pages/DocsPage.tsx`. Keep in sync when behavior or deploy paths change.
- **Build output:** static files suitable for **Vercel**, Netlify, Cloudflare Pages, or any static host.
- **CORS:** worker allows origins from **`STUDIO_CORS_ORIGINS`** (comma-separated or `*` for dev-only caution).

The marketing site, **`/studio`**, and **`/docs`** share the same app; routing is client-side (Vite SPA). **`vercel.json`** rewrites unknown paths to **`index.html`** so deep links work.

---

## Studio UI

- **Health:** probes the worker; shows configuration problems early.
- **API key:** when the worker has **`STUDIO_API_AUTH_REQUIRED=1`**, the UI stores **`Authorization` / `X-API-Key`** material in **`localStorage`** and sends it on API calls and zip downloads.
- **Mock mode:** runs the pipeline without Ollama (validated fake specs).
- **Textures:** requires a reachable ComfyUI instance compatible with worker env (`STUDIO_COMFY_URL`, checkpoint, profile `sd15` / `sdxl`).
- **Mesh export:** optional checkbox → worker runs headless Blender when configured.

**Auth model:** [api-keys-and-local-stack.md](./api-keys-and-local-stack.md).

---

## Python worker

- **Install from PyPI:** `pipx install immersive-studio` or `pip install immersive-studio` ([PyPI](https://pypi.org/project/immersive-studio/)).
- **Install from source (contributors):** `pip install -e .` from `apps/studio-worker` ([README](../../apps/studio-worker/README.md)).
- **Releases (maintainers):** [releasing.md](./releasing.md) — version bump, schema sync, tags, PyPI.
- **CLI entrypoint:** `immersive-studio` — `generate-spec`, `validate-spec`, `pack`, `run-job`, **`serve`** (FastAPI + uvicorn), **`queue-worker`**, **`tenants`** (create/list/issue-key/set-tier when SaaS mode is on).
- **Default data locations:** under repo **`output/`** (gitignored): `tenants.sqlite`, `queue.sqlite`, `jobs/`, `packs/` — unless overridden by env / path helpers ([`essentials.md`](./essentials.md) §1b).

**ComfyUI workflows:** versioned JSON under `apps/studio-worker/src/studio_worker/comfy_workflows/` — see [comfy/README.md](../../apps/studio-worker/comfy/README.md).

---

## HTTP API reference

All studio JSON routes are under **`/api/studio/…`** on the worker host.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/studio/health` | Liveness; `auth_required`, Stripe webhook flag |
| GET | `/api/studio/metrics` | Queue counts by status + `jobs_indexed` (tenant-scoped when auth on) |
| GET | `/api/studio/comfy-status` | ComfyUI probe (no API key) |
| GET | `/api/studio/usage` | Tier + monthly credits (key when auth on) |
| POST | `/api/studio/generate-spec` | Prompt → validated spec |
| POST | `/api/studio/pack` | Ad-hoc pack |
| POST | `/api/studio/jobs/run` | Synchronous full job |
| POST | `/api/studio/queue/jobs` | Enqueue async job |
| GET | `/api/studio/queue/jobs` | List queue rows |
| GET | `/api/studio/queue/jobs/{queue_id}` | Single queue row |
| GET | `/api/studio/jobs` | List persisted jobs |
| GET | `/api/studio/jobs/{job_id}/download` | `pack.zip` file or **302** to remote URL if blob storage enabled |
| GET | `/api/studio/paths` | Debug paths + `queue_backend`, `redis_queue_engine`, `tenants_backend`, `job_artifacts_backend`, `postgres_configured` |
| GET/POST | `/api/studio/billing/*` | Stripe Checkout, Portal, webhook |

**Authentication:** `Authorization: Bearer <key>` or **`X-API-Key`** when **`STUDIO_API_AUTH_REQUIRED=1`**.

**Authoritative tables and env tables:** [apps/studio-worker/README.md](../../apps/studio-worker/README.md).

---

## Environment variables and pip extras

The worker has **many** environment variables (Ollama, Comfy, Blender, quotas, moderation, auth, queue backends, Postgres, Redis, SQS, S3/Vercel Blob, Stripe, …).

- **Curated overview:** [essentials.md §3](./essentials.md) (selected vars) + pointer to worker README.
- **Full table:** [apps/studio-worker/README.md — Environment](../../apps/studio-worker/README.md#environment).

**Optional Python extras** (install from `apps/studio-worker`):

| Extra | Purpose |
|-------|---------|
| `dev` | pytest, respx, fakeredis |
| `postgres` | `psycopg` for Postgres queue/tenants |
| `redis` | `redis` client for Redis queue |
| `s3` | `boto3` for S3/R2 artifacts and SQS |
| `scale` | postgres + redis + boto3 together |

Example: `pip install -e ".[scale]"`.

---

## Data, queues, and horizontal scale

### Default (single VM)

| Store | Typical path | Role |
|-------|----------------|------|
| SQLite | `output/tenants.sqlite` | Tenants, API key hashes, credits, Stripe links, concurrency |
| SQLite | `output/queue.sqlite` | Async queue + idempotency |
| Filesystem | `output/jobs/` | Job folders, `pack.zip`, `index.json` |

SQLite uses **WAL** mode. **Backups:** snapshot tenants DB, queue DB, and `output/jobs/` together for coherent recovery.

### Managed / multi-replica options

| `STUDIO_QUEUE_BACKEND` | Needs | Behavior |
|------------------------|--------|----------|
| `sqlite` (default) | — | Local `queue.sqlite` |
| `postgres` | `DATABASE_URL` | Shared `queue_jobs` in Postgres; `SKIP LOCKED` claims |
| `redis` | `STUDIO_REDIS_URL` or `REDIS_URL` | Redis-backed queue; engine: **`STUDIO_REDIS_QUEUE_ENGINE=zset`** (sorted set) or **`streams`** (`XADD` / `XREADGROUP` / `XACK`) |
| `sqs` | `DATABASE_URL` + `STUDIO_SQS_QUEUE_URL` | Postgres rows + SQS wake messages |

| `STUDIO_TENANTS_BACKEND` | Needs | Behavior |
|--------------------------|--------|----------|
| `sqlite` (default) | — | Local `tenants.sqlite` |
| `postgres` | `DATABASE_URL` | Shared tenant tables |

| `STUDIO_JOB_ARTIFACTS` | Needs | Behavior |
|------------------------|--------|------------|
| `local` (default) | — | Serve `pack.zip` from disk |
| `s3` / R2 | Bucket + credentials (+ optional `STUDIO_S3_ENDPOINT_URL`) | Upload zip; download via presigned URL on job row |
| `vercel_blob` | `BLOB_READ_WRITE_TOKEN` | Upload via Vercel Blob HTTP API; download **302** |

**Vercel note:** the **static site** on Vercel does **not** host SQLite or job files. Set **`VITE_STUDIO_API_URL`** to your worker. Details: [essentials.md §1b](./essentials.md).

---

## Multi-tenant mode, API keys, and billing

- **`STUDIO_API_AUTH_REQUIRED=1`:** studio routes require a valid API key; jobs and queue rows are scoped by **`tenant_id`**.
- **Issuing keys:** `immersive-studio tenants create …` then **`tenants issue-key`** (raw key shown once).
- **Credits & tiers:** defined in worker code (`tiers.py`); Stripe webhooks map subscriptions to tiers. See worker README **Indie / multi-tenant tiers** and **`STUDIO_STRIPE_PRICE_*`**.
- **Webhooks:** `POST /api/studio/billing/webhook` uses **`STRIPE_WEBHOOK_SECRET`**.
- **Operations / email / monitoring:** [stripe-monitoring-and-emails.md](./stripe-monitoring-and-emails.md).

---

## Asset pipeline

1. **Spec:** JSON **`StudioAssetSpec`** validated against schema + studio rules ([json-schema-spec.md](./json-schema-spec.md)).
2. **Textures:** ComfyUI PBR-style passes; file naming `{variant}_{slot}_{role}.png` — see [essentials.md §2–3](./essentials.md).
3. **Mesh (optional):** Blender headless export — [essentials.md §5](./essentials.md), `STUDIO_BLENDER_*` env.
4. **Pack:** `manifest.json`, `spec.json`, `Textures/`, optional `Models/`, attribution files.
5. **Zip & index:** `pack.zip` + job index for listing and download.

**Style presets:** [art-style-presets.md](./art-style-presets.md). **Unity export conventions:** [unity-export-conventions.md](./unity-export-conventions.md).

---

## Unity importer

- **Package:** `com.immersivelabs.studio` — add as UPM local/git dependency.
- **Import:** menu **Immersive Labs → Import Studio Pack…** — select folder containing `manifest.json`.
- **Materials:** builds **`{pbr_base}_Lit.mat`** from texture groups; matches glTF material names from Blender when present.

Full guide: [packages/studio-unity/README.md](../../packages/studio-unity/README.md).

---

## Schema, types, and validation

- **Canonical JSON Schema:** `packages/studio-types/schema/studio-asset-spec-v0.1.schema.json`
- **TS package:** `@immersive/studio-types` — keep types in sync when the schema changes.
- **Draft / rationale:** [json-schema-spec.md](./json-schema-spec.md)

---

## Security, moderation, and hardening

- **Prompt blocklist, moderation toggles, quotas, attribution:** [hardening.md](./hardening.md) and worker env (`STUDIO_PROMPT_BLOCKLIST`, `STUDIO_MODERATION_DISABLED`, `STUDIO_QUOTAS_DISABLED`, job caps, …).
- **Phase 6 / roadmap context:** [phased-roadmap.md](./phased-roadmap.md).

---

## Operations: health, metrics, backups

| Endpoint / practice | Use |
|---------------------|-----|
| `GET /api/studio/health` | Uptime checks; `auth_required` for clients |
| `GET /api/studio/metrics` | Queue depth by status + indexed job count (for dashboards) |
| `GET /api/studio/paths` | Confirm `jobs_root`, DB paths, active backends |
| **Backups** | Snapshot `tenants.sqlite`, `queue.sqlite`, `output/jobs/` (and any remote bucket policy if using blob storage) |

---

## Deployment: Vercel, workers, and persistence

**Typical split**

1. **Build and deploy** `apps/web` to a static host (e.g. Vercel). This repo includes **`vercel.json`** at the monorepo root so the output directory is **`apps/web/dist`** (Vite’s build) and client-side routes (e.g. **`/studio`**) rewrite to **`index.html`**. In the Vercel dashboard, keep the project **root** at the repository root unless you move configuration; if you previously set **Output Directory** to `public`, remove that override so `vercel.json` applies.
2. Set **`VITE_STUDIO_API_URL`** in that project to the **public worker URL** (HTTPS).
3. Run **`immersive-studio serve`** (or gunicorn/uvicorn) on a **VM, container, or metal** with a **persistent volume** for `output/` (or equivalent for Postgres/Redis/S3 if you moved storage).

**Zero-cost VM path (GCP):** step-by-step **`e2-micro`**, Docker image from this repo, HTTPS (Cloudflare Tunnel or Caddy), and Vercel env vars — [deploy-gcp-free-vm.md](./deploy-gcp-free-vm.md).

**Checklist**

- [ ] Worker URL reachable from browsers (CORS).
- [ ] Persistent disk (or managed DB + blob) for anything you need after restart.
- [ ] Ollama / Comfy reachable **from the worker network**, not from Vercel edge.
- [ ] Stripe webhook URL points at worker **`/api/studio/billing/webhook`** if billing is enabled.

---

## Testing and CI

- **Worker tests:** from `apps/studio-worker`, `pip install -e ".[dev]"` then `python -m pytest`.
- **Monorepo:** root `npm run build` validates the web app build; CI expectations are described in [essentials.md](./essentials.md) where relevant.

---

## Full documentation index

| Document | What you get |
|----------|----------------|
| **Web `/docs`** (see [Web application](#web-application)) | User-facing hub: overview, deploy, ComfyUI, Blender, Unity — **apps/web** |
| **This manual** | End-to-end platform map + TOC |
| [essentials.md](./essentials.md) | Operator “single sheet”: storage, env highlights, Blender, Unity, API surface |
| [scripts/studio-cloudflare-tunnel/README.md](../../scripts/studio-cloudflare-tunnel/README.md) | GCE + Cloudflare script index, `STUDIO_COMFY_URL` notes |
| [architecture.md](./architecture.md) | Components, data flow, scale options |
| [README.md](./README.md) | Short planning folder intro + doc map |
| [vision-and-scope.md](./vision-and-scope.md) | Goals and non-goals |
| [phased-roadmap.md](./phased-roadmap.md) | Delivery phases and status |
| [DECISIONS.md](./DECISIONS.md) | Early technical decisions |
| [api-keys-and-local-stack.md](./api-keys-and-local-stack.md) | API key vs local-only operation |
| [art-style-presets.md](./art-style-presets.md) | Multiple visual styles |
| [json-schema-spec.md](./json-schema-spec.md) | Spec/manifest draft notes |
| [unity-export-conventions.md](./unity-export-conventions.md) | Units, folders, colliders |
| [hardening.md](./hardening.md) | Moderation, quotas, attribution, CI |
| [deploy-gcp-free-vm.md](./deploy-gcp-free-vm.md) | Free GCP `e2-micro`, Docker worker, HTTPS, Vercel |
| [cloudflare-edge-and-storage.md](./cloudflare-edge-and-storage.md) | Workers / R2 / D1 / KV vs Python VM; **R2** via existing env |
| [stripe-monitoring-and-emails.md](./stripe-monitoring-and-emails.md) | Billing operations |
| [apps/studio-worker/README.md](../../apps/studio-worker/README.md) | CLI, full HTTP table, **full env table**, Stripe setup, Blender |
| [apps/studio-worker/comfy/README.md](../../apps/studio-worker/comfy/README.md) | ComfyUI workflows and checkpoints |
| [packages/studio-unity/README.md](../../packages/studio-unity/README.md) | Unity importer usage |
| [packages/studio-types/README.md](../../packages/studio-types/README.md) | Shared types package |
| [Repository README](../../README.md) | Clone-level quick start |

---

*Last orientation: start with [Local development](#local-development-quick-path), then [HTTP API](#http-api-reference) through [Data and scale](#data-queues-and-horizontal-scale) for integration, then [Deployment](#deployment-vercel-workers-and-persistence) for production. For deep tables, keep [apps/studio-worker/README.md](../../apps/studio-worker/README.md) open alongside this page.*
