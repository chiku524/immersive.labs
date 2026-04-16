# Studio pipeline essentials

Single reference for **operators and integrators**: how the worker, packs, Blender mesh export, Unity import, billing, and CI fit together. For product vision and phased delivery, see [README.md](./README.md) and [phased-roadmap.md](./phased-roadmap.md).

---

## 1. Repository layout (short)

| Path | Role |
|------|------|
| `apps/web` | Vite + React — marketing site and **`/studio`** UI |
| `apps/studio-worker` | Python: spec, ComfyUI textures, jobs, queue, HTTP API, Stripe billing |
| `packages/studio-types` | JSON Schema + shared TS types for `StudioAssetSpec` |
| `packages/studio-unity` | Unity Editor package: import packs, PBR materials, optional box colliders |
| `docs/studio/` | Planning + this file |

---

## 1b. Storage and databases — do you need PostgreSQL?

**No.** The stock worker does **not** require PostgreSQL, MySQL, Redis, or any other server database. Everything ships with **embedded SQLite** plus the filesystem.

| Store | Default location | Role |
|-------|------------------|------|
| **SQLite** | `output/tenants.sqlite` | Tenants, hashed API keys, monthly credit counters, Stripe customer/subscription links |
| **SQLite** | `output/queue.sqlite` | Durable async queue (`pending` / `running` / `completed` / `dead`), idempotency keys |
| **Filesystem** | `output/jobs/` | Per-job directories, `pack.zip`, job `index.json`, quotas |

Paths can be redirected via the worker’s path helpers / env (see worker README). Both SQLite files use **WAL** mode for safer concurrent reads/writes.

**Backups:** snapshot `tenants.sqlite`, `queue.sqlite`, and `output/jobs/` together if you care about recovery (queue rows reference completed studio job IDs).

**Horizontal scale (optional, code paths exist):** set **`DATABASE_URL`** to a managed Postgres (e.g. from the [Vercel Marketplace](https://vercel.com/marketplace) or any host), then:

- **`STUDIO_QUEUE_BACKEND=postgres`** — shared `queue_jobs` table; workers use `FOR UPDATE SKIP LOCKED` claims.
- **`STUDIO_QUEUE_BACKEND=redis`** — jobs live in Redis (per-job hashes, idempotency keys, `WATCH`/`MULTI` mutex — no Redis Lua required). Set **`STUDIO_REDIS_URL`** or **`REDIS_URL`**. Install **`pip install -e ".[redis]"`**.
  - **`STUDIO_REDIS_QUEUE_ENGINE=zset`** (default): pending work is a **sorted set** (same semantics as before).
  - **`STUDIO_REDIS_QUEUE_ENGINE=streams`**: dispatch uses **Redis Streams** — **`XADD`** enqueue notifications, workers **`XREADGROUP`** with group **`STUDIO_REDIS_STREAM_GROUP`** (default `studio_workers`), **`XACK`** after success or failure; retries **`XADD`** a new stream entry. Tune **`STUDIO_REDIS_STREAM_BLOCK_MS`**, **`STUDIO_REDIS_STREAM_MAXLEN`**, and optional **`STUDIO_REDIS_STREAMS_PREFIX`** (defaults to `{queue_prefix}:sx` so zset and streams keys never collide).
- **`STUDIO_QUEUE_BACKEND=sqs`** — **`STUDIO_SQS_QUEUE_URL`** plus **`DATABASE_URL`**: Postgres remains the source of truth for rows (list, metrics, idempotency); **SQS** carries `{queue_id}` wake messages so workers long-poll instead of hammering the DB. Install **`pip install -e ".[scale]"`** or at least **`postgres` + `s3`** extras for `psycopg` and `boto3`.
- **`STUDIO_TENANTS_BACKEND=postgres`** — shared tenants, API keys, monthly credits, Stripe links, concurrency slots.

Install **`pip install -e ".[postgres]"`** in `apps/studio-worker` so `psycopg` is available when using Postgres.

**Blob storage for `pack.zip`:** with **`STUDIO_JOB_ARTIFACTS=s3`** (plus bucket + AWS-style credentials, optional **`STUDIO_S3_ENDPOINT_URL`** for R2) or **`STUDIO_JOB_ARTIFACTS=vercel_blob`** (plus **`BLOB_READ_WRITE_TOKEN`**), the worker uploads each zip after the job and stores a URL on the job index; **`GET …/jobs/{id}/download`** responds with **302** to that URL when present. Default **`local`** keeps zips only on disk (single-VM friendly).

**Redis** is optional (e.g. distributed rate limits); the queue is Postgres-backed when configured, not Redis.

### Vercel (or any static host) and SQLite

**The SQLite databases are not linked to a Vercel project.** Vercel builds and serves the **frontend** (`apps/web`). The **Python worker** is a separate process with its own filesystem (or volume). Typical setup:

1. Deploy the web app to Vercel; set **`VITE_STUDIO_API_URL`** in the Vercel project to your worker URL (e.g. `https://studio-api.example.com`).
2. Run **`immersive-studio serve`** (or gunicorn/uvicorn) on a host with a **persistent** `output/` directory so `tenants.sqlite`, `queue.sqlite`, and job folders survive restarts.

If the worker URL is wrong or the worker is down, the `/studio` page shows a health error — the SQLite files on your laptop are **not** used by Vercel.

### Observability (built-in)

- **`GET /api/studio/metrics`** — JSON with **`queue`** counts per status (`pending`, `running`, `completed`, `dead`, …), **`jobs_indexed`**, and **`slo`** (on SQLite: ages of the oldest claimable pending row and oldest running row — useful for alerting). Tenant-scoped when `STUDIO_API_AUTH_REQUIRED=1`; global counts in local dev mode. Responses use **`Cache-Control: no-store`** so proxies do not serve stale operator data. For splitting API vs queue under load, see [production-queue-split.md](./production-queue-split.md) and [security-operational-checklist.md](./security-operational-checklist.md).
- **`GET /api/studio/dashboard`** — Same **`usage`**, **`billing`**, **`jobs`**, **`worker_hints`**, and **`queue_slo`** payloads as the separate GETs / metrics SLO, in one response (see § Production API stability below). Also **`no-store`**.
- **Other tenant / operator GETs** — **`/api/studio/usage`**, **`/jobs`**, **`/queue/jobs`**, **`/billing/status`**, **`/paths`**, and successful **`/jobs/{id}/download`** responses send **`no-store`** for the same reason.

**Shipping updates:** [deploy-recent-changes.md](./deploy-recent-changes.md) — order for redeploying **studio-edge**, **web** (Vercel), and the **Python worker** on your host.

### Production API stability (Ollama, tunnel, VM capacity)

When **`https://api.…`** is fronted by **Cloudflare Worker → `ORIGIN_URL` (tunnel host) → FastAPI** on a **small VM**, intermittent **502**/**524** HTML from the tunnel is common if the box is saturated. Mitigations:

1. **Ollama (LLM spec)**  
   - Prefer a **smaller/faster** model (`STUDIO_OLLAMA_MODEL`, e.g. `tinyllama`), **`mock`** on the `/studio` UI for layout testing, or server-side **`STUDIO_OLLAMA_DISABLED=1`** so the worker always uses deterministic mock specs (queue + API + CLI) when no local LLM is available.  
   - **`STUDIO_OLLAMA_READ_TIMEOUT_S`** (seconds, **15–3600**, default **600** when unset from **0.1.9**): base read timeout per Ollama `/api/chat` attempt; the worker **retries once** after a read timeout with a longer second read (~**1.5×** base, each attempt hard-capped at **3600s** in code). With **streaming on by default** (`STUDIO_OLLAMA_STREAM` unset), read timeouts apply between NDJSON chunks, which is usually more forgiving than a single blocking response (`STUDIO_OLLAMA_STREAM=0`).  
   - **`STUDIO_OLLAMA_CONNECT_TIMEOUT_S`** (default **8s**, clamp **2–60**): TCP connect timeout for every Ollama HTTP call — fails fast when nothing listens on **`STUDIO_OLLAMA_URL`**.  
   - **`STUDIO_OLLAMA_PREFLIGHT`** (default **on**): before each LLM call, **`GET /api/tags`** with a short deadline so a dead Ollama errors in seconds instead of burning a full read cycle. Set **`STUDIO_OLLAMA_PREFLIGHT=0`** to skip.  
   - **`STUDIO_OLLAMA_VERIFY_MODEL`** (default **on**): after `/api/tags`, ensure **`STUDIO_OLLAMA_MODEL`** appears in **`ollama list`** (e.g. `tinyllama` matches `tinyllama:latest`). Set **`STUDIO_OLLAMA_VERIFY_MODEL=0`** for exotic tag names.  
   - **`STUDIO_OLLAMA_NUM_PREDICT`** (default **2048**) caps output length (raise if JSON truncates). **`STUDIO_OLLAMA_JSON_FORMAT`** (default on) sends **`format: json`**. Optional **`STUDIO_OLLAMA_KEEP_ALIVE`** (e.g. `30m`) reduces cold-start latency. **`GET /api/studio/dashboard` → `worker_hints`** exposes effective timeouts and flags (`ollama_connect_timeout_s`, `ollama_preflight`, `ollama_verify_model`, `ollama_disabled`). If you still see **~900s** read behavior, **GCE metadata** or Docker env may still pin **`STUDIO_OLLAMA_READ_TIMEOUT_S=900`** — raise or remove it.  
   - Add **RAM/swap** if Ollama swaps under Comfy + Blender.

2. **Tunnel / DNS**  
   - Keep the **tunnel hostname** used in **`ORIGIN_URL`** (e.g. **`api-origin`**) on **DNS only (grey cloud)** — proxied orange cloud adds timeouts. See [apps/studio-edge/README.md](../../apps/studio-edge/README.md) and [scripts/studio-cloudflare-tunnel/add-tunnel-cname.sh](../../scripts/studio-cloudflare-tunnel/add-tunnel-cname.sh) (`CLOUDFLARE_TUNNEL_CNAME_PROXIED=false`).  
   - Watch **`cloudflared`** and **`uvicorn`/Docker** logs when 502s appear.

3. **Capacity**  
   - **Ollama + ComfyUI + Blender** on one **e2-micro**-class host routinely causes **read timeouts** and **HTTP 502** bursts. Upgrade the VM, run **`STUDIO_EMBEDDED_QUEUE_WORKER=0`** with a **separate** `immersive-studio queue-worker` process, or offload Comfy to another machine (`STUDIO_COMFY_URL`).  
   - **Embedded consumer lifecycle:** with **`STUDIO_EMBEDDED_QUEUE_WORKER=1`**, the API starts a background queue poller. On **process shutdown** (SIGTERM, container stop, or FastAPI **`TestClient`** teardown), the worker signals that loop to exit and **joins** the thread briefly so a stray consumer does not keep running after the app context or patched DB paths change (important for tests and rolling deploys). If a deploy **kills the process while a job is mid-flight**, the queue row can remain **`running`** forever (dashboard “running for hours”). From **0.1.8**, the API runs **`reclaim_stale_running_jobs()`** on startup (SQLite): rows **`running`** longer than **`STUDIO_QUEUE_STALE_RUNNING_RECLAIM_S`** seconds since **`updated_at`** revert to **`pending`** for retry (default **43200** = 12h; set **0** to disable).

4. **Fewer round-trips**  
   - **`GET /api/studio/dashboard`** returns **`usage`**, **`billing`**, **`jobs`**, **`worker_hints`**, and **`queue_slo`** (same fields as **`GET /api/studio/metrics` → `slo`**) in one JSON object. The `/studio` page uses this to reduce parallel GETs through the Worker and to show tuning context next to recent jobs.

5. **Errors that look like two different failures**  
   - **`No JSON object found in model output`** comes from **`POST /api/studio/generate-spec`** (or the spec step inside a full job): Ollama returned prose, an empty body, or malformed JSON. It is unrelated to **`502`** from the edge unless the browser retried spec generation while the tunnel was unhealthy.  
   - **`Gateway or tunnel returned HTTP 502 HTML…`** means **`api.immersivelabs.space`** (Cloudflare Worker) could not get JSON from **`ORIGIN_URL`** (usually **`https://api-origin…`**). Fix origin health and DNS (grey cloud on **`api-origin`**) first; the studio-edge Worker already retries idempotent **`GET /api/studio/*`** a few times on transient 5xx.

---

## 2. Asset spec and naming

- Canonical schema: `packages/studio-types/schema/studio-asset-spec-v0.1.schema.json`.
- **`asset_id`**: snake_case identifier; drives folder names under `Models/` and `Textures/`.
- **Textures** (worker output): `{variant_id}_{slot_id}_{role}.png` with `role` ∈ `albedo`, `normal`, `orm` (see `texture_pipeline.py`).
- **PBR material base key**: `{variant_id}_{slot_id}` — must match across textures, generated Unity **`{base}_Lit.mat`**, and (when mesh export runs) **glTF material names** from Blender.

---

## 3. Worker environment (selected)

| Variable | Purpose |
|----------|---------|
| `STUDIO_REPO_ROOT` | Monorepo root (auto-detected if unset) |
| `STUDIO_OLLAMA_URL` / `STUDIO_OLLAMA_MODEL` | LLM for spec generation |
| `STUDIO_OLLAMA_DISABLED` | `1` / `true` / `on` → worker uses mock specs (no Ollama) for jobs and generate-spec |
| `STUDIO_OLLAMA_READ_TIMEOUT_S` / connect / preflight / verify | See § Production API stability — defaults **600s** read, **8s** connect, preflight + model verify **on** (**0.1.9+**) |
| `STUDIO_COMFY_URL` / `STUDIO_COMFY_CHECKPOINT` / `STUDIO_COMFY_PROFILE` | ComfyUI (`sd15` / `sdxl`). **When unset, defaults to `https://comfy.immersivelabs.space`.** If the worker runs **in Docker** and ComfyUI on the **host**, do **not** use `http://127.0.0.1:8188` (that is the container, not the host) — use the **public HTTPS URL** or `http://host.docker.internal:8188` with Docker’s host gateway. For ComfyUI on the **same machine as the Python process** (no Docker), `http://127.0.0.1:8188` is fine. |
| `STUDIO_TEXTURE_MAX_IMAGES` | Cap ComfyUI images per job |
| `STUDIO_JOBS_MAX_COUNT` / `STUDIO_JOBS_MAX_TOTAL_BYTES` | Job store quotas |
| `STUDIO_API_AUTH_REQUIRED` | `1` → API keys + tenant isolation |
| `STUDIO_CORS_ORIGINS` | Browser origins for `/studio` |
| `STUDIO_BLENDER_BIN` | Blender executable if not on `PATH` |
| `STUDIO_BLENDER_TIMEOUT_S` | Headless mesh export timeout (seconds) |
| `STUDIO_EXPORT_MESH_DEFAULT` | `1`/`true` → mesh export on every job unless disabled in request |
| `DATABASE_URL`, `STUDIO_*_BACKEND`, `STUDIO_REDIS_QUEUE_ENGINE`, `STUDIO_JOB_ARTIFACTS`, S3 / Blob tokens | Optional Postgres / Redis / SQS queue + tenants + remote `pack.zip` — see §1b and worker README |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STUDIO_STRIPE_PRICE_*` | Billing — see [apps/studio-worker/README.md](../../apps/studio-worker/README.md) |

Full tables: [apps/studio-worker/README.md](../../apps/studio-worker/README.md).

---

## 4. Pack layout (job output)

Typical folder (or zip contents):

- `manifest.json` — job id, toolchain, embedded asset specs  
- `spec.json` — primary `StudioAssetSpec` (when written)  
- `Textures/<asset_id>/…` — PNGs  
- `Models/<asset_id>/<asset_id>.glb` — optional placeholder from Blender  
- `UnityImportNotes.md`, `ATTRIBUTION.md` / `licenses.json` when enabled  

---

## 5. Blender mesh export (`studio_worker/blender/export_mesh.py`)

- **CLI**:  
  `blender --background --python <path-to>/studio_worker/blender/export_mesh.py -- --spec <pack>/spec.json --output out.glb`
- **Shared PBR logic**: [`studio_worker/pbr_keys.py`](../../apps/studio-worker/src/studio_worker/pbr_keys.py) defines **`ordered_pbr_material_bases`**, **`primary_pbr_material_base`**, and **`mat_name_for_part`** (also used by ComfyUI role sets via `GENERATED_ROLES`). The Blender script prepends `apps/studio-worker/src` to `sys.path` and imports this module so keys stay aligned with Python and Unity.
- **Profiles** (`category`): `prop` (stacked boxes + horizontal **cylinder band** between base and top), `environment_piece` (platform), `character_base` (legs + torso + **UV sphere head**), `material_library` (swatch), else a single beveled cube.
- **Tags:** add `minimal_placeholder` or `single_stack` to **`tags`** on the spec to get a **two-part** prop (no band) for lighter GLBs.
- **Materials**: Multi-part meshes assign **`mat_name_for_part(bases, part_index)`** so the first part uses `bases[0]`, the second `bases[1 % len(bases)]`, etc. Single-part meshes use one base.
- **Export**: Multiple mesh objects are parented under an **Empty** (`{asset_id}_root`); GLB export uses **full scene** export when the root is an Empty so all children are included.

Worker integration: [mesh_export.py](../../apps/studio-worker/src/studio_worker/mesh_export.py), CLI/API `export_mesh`, env vars above.

---

## 6. Unity import (`packages/studio-unity`)

1. **Immersive Labs → Import Studio Pack…** — select the folder that contains `manifest.json`.  
2. Textures are copied; **`Materials/{pbr_base}_Lit.mat`** are built from albedo/normal/ORM groups.  
3. **glTF materials**: Importer matches imported material names to PBR bases, then falls back to **ordered** Lit materials, then preferred/first material (see package README).  
4. **Box colliders**: If `unity.collider == "box"` on the manifest asset, a **BoxCollider** is added/updated on each imported `.glb` / `.gltf` root using renderer bounds or `target_height_m`. Manual menu: **Immersive Labs → Apply Box Collider From spec.json…** still works for ad-hoc selection.

Requirements: URP recommended; optional **ImmersiveStudio/Packed ORM Lit** for packed ORM maps.

---

## 7. HTTP API (worker)

- Health: `GET /api/studio/health`  
- Run job: `POST /api/studio/jobs/run` (optional `export_mesh`, `textures`, etc.)  
- Queue: `POST /api/studio/queue/jobs`  
- Billing: `/api/studio/billing/*` — see worker README  

Clients send `Authorization: Bearer <api_key>` or `X-API-Key` when auth is required.

---

## 8. CI (GitHub Actions)

| Workflow | Purpose |
|----------|---------|
| [studio-worker.yml](../../.github/workflows/studio-worker.yml) | pytest on Python 3.12 |
| [studio-worker-blender.yml](../../.github/workflows/studio-worker-blender.yml) | Pinned **Blender 4.2.x** Linux tarball + cache + headless `export_mesh.py` smoke |
| [studio-worker-gpu-comfy.yml](../../.github/workflows/studio-worker-gpu-comfy.yml) | Optional GPU/Comfy: `workflow_dispatch` can select **`self-hosted`** runner + secrets |

The Blender workflow downloads a fixed release from `download.blender.org` and caches the extracted folder between runs. Override locally with `STUDIO_BLENDER_BIN` or a self-hosted runner.

---

## 8b. Async queue idempotency

`POST /api/studio/queue/jobs` accepts optional **`idempotency_key`** (≤128 chars, per tenant).

- First request with a key **inserts** a row and charges credits (when limits apply).
- Repeat requests with the same key return the **same** `queue_id` with **`deduplicated: true`** and **do not** charge again while the row still exists with that key.
- When a job reaches **`dead`** after max retries, the key is **cleared** so clients can enqueue a new attempt with the same key.

Implementation: `studio_worker/sqlite_queue.py` (`idempotency_key` column + unique index on `coalesce(tenant_id,''), idempotency_key`), `tenants_db.refund_credits` if a race forces dedup after credits were charged.

---

## 9. Stripe and tenants (pointer)

Subscriptions map to tenant tiers via webhooks; local testing via Stripe CLI. Details: [apps/studio-worker/README.md](../../apps/studio-worker/README.md) (Stripe section) and [stripe-monitoring-and-emails.md](./stripe-monitoring-and-emails.md).

---

## 10. Troubleshooting

| Symptom | Check |
|---------|--------|
| No `.glb` in pack | Blender on `PATH` or `STUDIO_BLENDER_BIN`; `mesh_logs` / `manifest.toolchain.mesh_pipeline` |
| Unity pink materials | URP Lit shader; ORM shader missing → fallback warning in Console |
| Wrong texture on mesh | PBR base keys align: filenames, `{base}_Lit`, glTF material names |
| Collider wrong size | Import applies box to **glTF root**; use menu command with selection if you need a child object |

---

## 11. Related docs

- [architecture.md](./architecture.md) — components and data flow  
- [unity-export-conventions.md](./unity-export-conventions.md) — folder and unit conventions  
- [api-keys-and-local-stack.md](./api-keys-and-local-stack.md) — local vs keyed API usage  
- [hardening.md](./hardening.md) — quotas, moderation, attribution  
