# Immersive Studio (CLI + SDK)

Publishable **PyPI** package **`immersive-studio`**: the **`immersive-studio`** terminal command, importable Python SDK **`immersive_studio`**, and the same **FastAPI** worker used by the **Video Game Generation Studio** (`/studio` in `@immersive/web`). Features include Ollama/mock spec generation, **ComfyUI** texture passes, optional **Blender** placeholder `.glb`, **Unity** pack layout (`manifest.json`, `spec.json`, `pack.zip`), and the **HTTP API**.

## Install (PyPI — like any other CLI)

After the package is published on PyPI as **`immersive-studio`** (maintainers: see **Publishing** below), end users can install globally with [**pipx**](https://pipx.pypa.io/) so the executable lands on `PATH` without touching system Python:

```bash
pipx install immersive-studio
immersive-studio doctor
```

Or into the active virtual environment:

```bash
pip install immersive-studio
python -m studio_worker.cli doctor
```

**Optional extras:** `pip install immersive-studio[postgres]`, `[redis]`, `[s3]`, or `[scale]` for production-style backends (see Environment table below).

> **Note:** The distribution was previously named `immersive-studio-worker`. Use **`immersive-studio`** going forward.

## Python SDK

```python
from immersive_studio import __version__, run_studio_job

result = run_studio_job(
    user_prompt="wooden barrel",
    category="prop",
    style_preset="toon_bold",
    use_mock=True,
    generate_textures=False,
    unity_urp_hint="6000.0.x LTS (pin when smoke-tested)",
    export_mesh=False,
)
print(result["job_id"], result["zip_path"])
```

Public symbols: `__version__`, `run_studio_job`, `validate_asset_spec_file`, `generate_asset_spec_with_metadata`, `comfy_base_url`, `comfy_reachability`. Advanced integrations can import from the `studio_worker` package directly.

## Publishing to PyPI

I cannot create or “register” a PyPI project on your behalf (that requires you to sign in at [pypi.org](https://pypi.org) and complete the flow below). You already have an account — use it to create the project and trusted publisher.

### Trusted publishing (GitHub Actions)

1. On **PyPI**, open **Account settings → Publishing** (or your project → **Publishing** once the project exists) and add a **pending** trusted publisher for **GitHub** before the first successful upload from Actions.
2. In the form, set **Repository name** to your GitHub repo exactly, e.g. `your-username/immersive.labs`.
3. **Workflow name** must be the **workflow file name** under `.github/workflows/`, including the extension:

   **`publish-immersive-studio.yml`**

   If PyPI shows *“Workflow name must end with .yml or .yaml”*, you almost certainly pasted the workflow’s **display title** from the YAML (`name: …` inside the file) instead of the **filename**. Use **`publish-immersive-studio.yml`** only.

4. **Environment name** can be left blank unless you use a GitHub **Environment** in the workflow (this repo’s publish workflow does not require one).

5. Merge this workflow to your default branch, then run **Actions → “PyPI publish (immersive-studio package)” → Run workflow**, or publish a **GitHub Release** to trigger it.

6. If the workflow fails with **`invalid-publisher`** / “no corresponding publisher”, re-check the three strings on PyPI (**owner/repo**, **`publish-immersive-studio.yml`**, and **environment**). The OIDC token from GitHub includes `environment: MISSING` unless you add `environment: …` to the workflow job; on PyPI the **Environment name** field must be **empty** to match, unless you intentionally configure both sides to the same name.

7. **Fastest unblock:** create a PyPI **API token** with upload scope, add a GitHub repository secret named **`PYPI_API_TOKEN`**, and re-run the workflow. The publish step passes `password: ${{ secrets.PYPI_API_TOKEN }}`; when the secret is set, uploads use the token (you can still keep trusted publishing configured for later).

### Manual upload (API token)

From `apps/studio-worker` with [build](https://pypi.org/project/build/) and [twine](https://twine.readthedocs.io/):

```bash
pip install build twine
python -m build
twine upload dist/*
```

Use a [PyPI API token](https://pypi.org/manage/account/token/) with upload scope; the first upload can create the project if the name is free.

If the project name **`immersive-studio`** is already taken on PyPI, change `name` in `pyproject.toml` to an available name (for example `immersive-labs-studio`) and update install docs accordingly.

When you change **`packages/studio-types/schema/studio-asset-spec-v0.1.schema.json`**, copy the file to **`src/studio_worker/data/studio-asset-spec-v0.1.schema.json`** before releasing so the wheel matches the canonical schema.

## Setup (monorepo / contributors)

From repository root:

```bash
cd apps/studio-worker
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

**Invoking the CLI:** After `pip install -e .`, the `immersive-studio` command lives next to your Python interpreter (for example `.venv\Scripts\immersive-studio.exe`, or `%APPDATA%\Python\Python3xx\Scripts\immersive-studio.exe` when pip used a **user** install). If your shell says `command not found`, either add that `Scripts` folder to your **PATH**, or call the module directly (works from any directory once the package is installed):

```bash
python -m studio_worker.cli doctor
```

From this app directory you can also use the repo wrappers (no PATH change):

```bash
./scripts/immersive-studio.sh doctor          # Git Bash / MSYS
scripts\immersive-studio.cmd doctor            # cmd.exe / PowerShell
```

Ensure [Ollama](https://ollama.com/) is running locally if you use LLM generation (default `http://127.0.0.1:11434`). Pull a JSON-capable model, for example:

```bash
ollama pull llama3.2
```

For **texture generation**, run [ComfyUI](https://github.com/comfyanonymous/ComfyUI) (default `http://127.0.0.1:8188`) and install a checkpoint that matches `STUDIO_COMFY_CHECKPOINT`. See [`comfy/README.md`](./comfy/README.md).

After installing ComfyUI and (for mesh export) [Blender](https://www.blender.org/), verify the worker can see both:

```bash
python -m studio_worker.cli doctor
```

Exit code `0` means ComfyUI answered at `STUDIO_COMFY_URL` (default `http://127.0.0.1:8188`) and Blender was resolved (PATH, `STUDIO_BLENDER_BIN`, or a standard Windows/macOS install path). Use `python -m studio_worker.cli doctor --comfy-url http://host:8188` to probe a different URL once.

To launch ComfyUI from a git checkout once dependencies are installed, set **`COMFYUI_ROOT`** and run [`scripts/start-comfyui-dev.sh`](./scripts/start-comfyui-dev.sh) or [`scripts/start-comfyui-dev.ps1`](./scripts/start-comfyui-dev.ps1) (listens on `127.0.0.1:8188`).

## Docker (VM / production-shaped)

The image copies **`packages/studio-types/schema`** and **`apps/studio-worker`** into a layout that matches `STUDIO_REPO_ROOT` (defaults to **`/repo`** in the image).

**Build** (from **monorepo root**):

```bash
docker build -f apps/studio-worker/Dockerfile -t immersive-studio-worker:local .
```

**Run** (set CORS to every **browser origin** that loads `/studio` — comma-separated, no trailing slashes):

```bash
docker run -d --name studio-worker --restart unless-stopped \
  -p 8787:8787 \
  -e STUDIO_CORS_ORIGINS='https://YOUR-APP.vercel.app,https://www.yourdomain.com,https://yourdomain.com' \
  -v studio-output:/repo/apps/studio-worker/output \
  immersive-studio-worker:local
```

If you only use the default Vercel hostname, a single origin is enough: `https://YOUR-APP.vercel.app`. Trailing slashes in the env var are ignored.

On a cloud VM behind **Cloudflare Tunnel**, bind Docker to localhost only: **`-p 127.0.0.1:8787:8787`** (see [deploy-gcp-free-vm.md](../../docs/studio/deploy-gcp-free-vm.md)).

**Compose** (dev smoke test; overrides `STUDIO_CORS_ORIGINS` as needed):

```bash
docker compose -f apps/studio-worker/docker-compose.yml up --build
```

**Free GCP VM + HTTPS + Vercel:** [docs/studio/deploy-gcp-free-vm.md](../../docs/studio/deploy-gcp-free-vm.md) (includes **`scripts/studio-cloudflare-tunnel/`** for `gcloud` + **Cloudflare Tunnel**).

## CLI

In the examples below, `immersive-studio` is shorthand for **`python -m studio_worker.cli`** (or the `.exe` on your PATH after you add Python’s `Scripts` folder — see **Setup**).

```bash
# Generate spec via Ollama (default model from env STUDIO_OLLAMA_MODEL or llama3.2)
immersive-studio generate-spec --prompt "wooden crate with iron bands" --style-preset toon_bold --category prop

# Validated mock spec without Ollama (CI / offline)
immersive-studio generate-spec --mock --prompt "neon barrel" --style-preset anime_stylized --category prop

# Validate a JSON file against schema + studio rules
immersive-studio validate-spec --file ./spec.json

# Write pack folder: manifest.json, spec.json, UnityImportNotes.md, Models/ + Textures/ layout
immersive-studio pack --spec ./spec.json --output ./out/MyPack

# Full persisted job under output/jobs/ (spec + pack + zip + index); optional ComfyUI textures
immersive-studio run-job --mock --prompt "wooden barrel" --textures

# Optional: ComfyUI on a non-default URL for this run only
immersive-studio run-job --mock --prompt "wooden barrel" --textures --comfy-url http://127.0.0.1:8188

# Same, plus headless Blender placeholder `.glb` under Models/ (requires Blender on PATH or STUDIO_BLENDER_BIN)
immersive-studio run-job --mock --prompt "crate" --export-mesh

# Check ComfyUI + Blender before a full job
immersive-studio doctor

# HTTP API for the web UI (CORS allows Vite dev server)
immersive-studio serve --host 127.0.0.1 --port 8787

# Poll SQLite-backed job queue (run multiple terminals or processes for parallel workers)
immersive-studio queue-worker --worker-id worker-a
immersive-studio queue-worker --once --worker-id one-shot

# Multi-tenant / indie SaaS (after STUDIO_API_AUTH_REQUIRED=1 on the server)
immersive-studio tenants create --name "Pixel Friends" --tier indie
immersive-studio tenants issue-key --tenant-id <uuid-from-create> --label "lead-dev-laptop"
immersive-studio tenants list
immersive-studio tenants set-tier --tenant-id <uuid> --tier team
```

## HTTP API (selected)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/studio/health` | Worker liveness (`auth_required` flag for clients) |
| GET | `/api/studio/metrics` | Queue counts by status + `jobs_indexed` (tenant-scoped when auth on) |
| GET | `/api/studio/comfy-status` | ComfyUI `/system_stats` probe (no API key) |
| GET | `/api/studio/usage` | Tier + monthly credits used/cap (requires key when auth on) |
| POST | `/api/studio/generate-spec` | Prompt → validated spec |
| POST | `/api/studio/pack` | Ad-hoc pack (scoped under `output/packs/…` when auth on) |
| POST | `/api/studio/jobs/run` | Full job → `output/jobs/job_*/` + `pack.zip` + index |
| POST | `/api/studio/queue/jobs` | Enqueue async job (SQLite or Postgres); optional `idempotency_key` dedupes per tenant; response `deduplicated` |
| GET | `/api/studio/queue/jobs` | Recent queue rows (tenant-scoped when auth on) |
| GET | `/api/studio/queue/jobs/{queue_id}` | Single queue row |
| GET | `/api/studio/jobs` | List persisted jobs + `jobs_root` path (tenant-scoped when auth on) |
| GET | `/api/studio/jobs/{job_id}/download` | Download `pack.zip` (local file) or **302** to a remote URL when `STUDIO_JOB_ARTIFACTS` uploads zips |
| GET | `/api/studio/paths` | Debug paths + active backends (`queue_backend`, `redis_queue_engine` when Redis, `tenants_backend`, …) |
| GET | `/api/studio/billing/status` | Stripe readiness + linked customer (requires key when auth on) |
| POST | `/api/studio/billing/checkout-session` | Returns Stripe Checkout URL for `{ "tier": "indie" \| "team" }` |
| POST | `/api/studio/billing/portal-session` | Returns Stripe Customer Portal URL (manage/cancel) |
| POST | `/api/studio/billing/webhook` | Stripe webhooks (signing secret); **no API key** |

Remote clients send **`Authorization: Bearer <api_key>`** or **`X-API-Key`**. The `/studio` UI stores an optional key in `localStorage` and uses it for fetch + zip download.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `STUDIO_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama base URL |
| `STUDIO_OLLAMA_MODEL` | `llama3.2` | Chat model name |
| `STUDIO_REPO_ROOT` | — | When set, writable job/queue data uses `apps/studio-worker/output` under this monorepo root (Docker / local dev). |
| `STUDIO_WORKER_DATA_DIR` | — | Override writable root for jobs, `queue.sqlite`, and `tenants.sqlite` (default: `~/.immersive-studio/worker` when `STUDIO_REPO_ROOT` is unset). |
| `STUDIO_COMFY_URL` | `http://127.0.0.1:8188` | ComfyUI server |
| `STUDIO_COMFY_PROFILE` | `sd15` | `sd15` or `sdxl` (selects workflow + latent size) |
| `STUDIO_COMFY_CHECKPOINT` | profile-specific | Checkpoint **file name** as shown in ComfyUI |
| `STUDIO_TEXTURE_MAX_IMAGES` | `32` | Cap variant×slot ComfyUI renders per job (albedo/normal/orm) |
| `STUDIO_JOBS_MAX_COUNT` | `200` | Index cap; oldest job folders deleted when trimming |
| `STUDIO_JOBS_MAX_TOTAL_BYTES` | `5368709120` | Target max bytes under `output/jobs/` before pruning |
| `STUDIO_QUOTAS_DISABLED` | — | Set to `1` to skip quota enforcement |
| `STUDIO_PROMPT_BLOCKLIST` | — | Comma-separated substrings to block in prompts |
| `STUDIO_MODERATION_DISABLED` | — | Set to `1` to skip moderation |
| `STUDIO_API_AUTH_REQUIRED` | off | Set to `1` to require API keys for studio routes (indie SaaS mode) |
| `STUDIO_CORS_ORIGINS` | Vite dev origins | Comma-separated browser origins, or `*` for any (use carefully in production) |
| `STRIPE_SECRET_KEY` | — | Secret API key (Dashboard → Developers) — required for Checkout / Portal |
| `STRIPE_WEBHOOK_SECRET` | — | Webhook signing secret for `POST /api/studio/billing/webhook` |
| `STRIPE_API_VERSION` | account default | Optional; pin Stripe API version string if you need stability |
| `STUDIO_STRIPE_PRICE_INDIE` | — | Stripe **Price** id for Indie recurring plan |
| `STUDIO_STRIPE_PRICE_TEAM` | — | Stripe **Price** id for Small team recurring plan |
| `STUDIO_STRIPE_PRICE_MAP` | — | Optional `price_abc:indie,price_def:team` overrides / extra prices |
| `STUDIO_BILLING_SUCCESS_URL` | `/studio?billing=success` | Checkout success redirect (optional: add `{CHECKOUT_SESSION_ID}` per Stripe docs) |
| `STUDIO_BILLING_CANCEL_URL` | `/studio?billing=cancel` | Checkout cancel redirect |
| `STUDIO_BILLING_PORTAL_RETURN_URL` | `/studio` | Customer Portal return URL |
| `STUDIO_BLENDER_BIN` | — | Path to `blender` executable if not on `PATH` |
| `STUDIO_BLENDER_TIMEOUT_S` | `180` | Max seconds for headless Blender mesh export |
| `STUDIO_EXPORT_MESH_DEFAULT` | off | Set to `1` / `true` to run mesh export on every `run-job` when the client does not pass `export_mesh` |
| `DATABASE_URL` | — | Postgres connection string (e.g. Vercel Postgres, Neon). Required when using Postgres backends below. |
| `STUDIO_QUEUE_BACKEND` | `sqlite` | `postgres` (shared rows in Postgres), `redis` (Redis broker + hashes), or `sqs` (SQS long-poll + Postgres rows — needs `DATABASE_URL`). |
| `STUDIO_REDIS_URL` / `REDIS_URL` | — | Broker URL when `STUDIO_QUEUE_BACKEND=redis`. |
| `STUDIO_REDIS_QUEUE_ENGINE` | `zset` | With Redis queue: `zset` (sorted-set dispatch) or `streams` (`XADD` / `XREADGROUP` / `XACK`). |
| `STUDIO_REDIS_STREAMS_PREFIX` | `{STUDIO_REDIS_QUEUE_PREFIX}:sx` | Key namespace for Streams mode (isolated from zset keys). |
| `STUDIO_REDIS_STREAM_GROUP` | `studio_workers` | Redis consumer group name for Streams mode. |
| `STUDIO_REDIS_STREAM_BLOCK_MS` | `5000` | `XREADGROUP` block timeout (ms). |
| `STUDIO_REDIS_STREAM_MAXLEN` | `50000` | Approximate `MAXLEN` on the dispatch stream (`~`). |
| `STUDIO_REDIS_QUEUE_PREFIX` | `studio:q` | Key namespace for the Redis queue. |
| `STUDIO_REDIS_QUEUE_MAX_TIMELINE` | `5000` | Cap on timeline index entries (oldest trimmed). |
| `STUDIO_SQS_QUEUE_URL` | — | Standard or FIFO SQS queue URL when `STUDIO_QUEUE_BACKEND=sqs` (Postgres holds job metadata). |
| `STUDIO_SQS_WAIT_SECONDS` | `20` | SQS `ReceiveMessage` long-poll wait (max 20). |
| `STUDIO_SQS_VISIBILITY_TIMEOUT` | `900` | Visibility timeout for in-flight SQS messages (seconds). |
| `STUDIO_SQS_ENDPOINT_URL` | — | Optional (e.g. LocalStack). |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | `us-east-1` | SQS client region when using `sqs` backend. |
| `STUDIO_TENANTS_BACKEND` | `sqlite` | Set `postgres` with `DATABASE_URL` for shared tenants / API keys / usage. |
| `STUDIO_JOB_ARTIFACTS` | `local` | `s3` (S3-compatible, incl. R2 via endpoint), or `vercel_blob` to upload `pack.zip` after each job. |
| `STUDIO_S3_BUCKET` | — | Bucket name when `STUDIO_JOB_ARTIFACTS=s3` (or `r2`). |
| `STUDIO_S3_REGION` | `auto` | AWS region; use `auto` for Cloudflare R2. |
| `STUDIO_S3_ENDPOINT_URL` | — | Custom endpoint URL (set for R2 / MinIO). |
| `STUDIO_S3_KEY_PREFIX` | `immersive-studio/packs` | Prefix for object keys (`{prefix}/{folder}/pack.zip`). |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | — | Standard boto3 credentials for S3/R2 (or instance role). |
| `BLOB_READ_WRITE_TOKEN` | — | Vercel Blob store read-write token when `STUDIO_JOB_ARTIFACTS=vercel_blob`. |

**Optional pip extras:** `pip install -e ".[postgres]"` (`psycopg`), `pip install -e ".[redis]"` (`redis` client), `pip install -e ".[s3]"` (`boto3`), or `pip install -e ".[scale]"` (Postgres + Redis + S3 deps together).

## Stripe Billing (subscriptions → tiers)

Operations (monitoring, trial emails, optional notify URL): [docs/studio/stripe-monitoring-and-emails.md](../../docs/studio/stripe-monitoring-and-emails.md).

Python dependency: **`stripe`** (declared in `pyproject.toml`). Flow:

1. **Stripe Dashboard:** create **Products** with recurring **Prices** (e.g. monthly). Copy each **Price id** (`price_…`) into `STUDIO_STRIPE_PRICE_INDIE` / `STUDIO_STRIPE_PRICE_TEAM`, *or* set **`metadata.tier`** on the Price to `indie` / `team` / `free` (overrides id mapping).
2. **Enable Customer portal** (Billing → Customer portal) so `POST /api/studio/billing/portal-session` works.
3. **Webhooks:** add endpoint `https://<your-host>/api/studio/billing/webhook` and subscribe at minimum to:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`  
   Paste the webhook **signing secret** into `STRIPE_WEBHOOK_SECRET`.
4. **Runtime env:** `STRIPE_SECRET_KEY`, `STUDIO_API_AUTH_REQUIRED=1`, tenant + API key as today.
5. **Indie group:** `tenants create` → `tenants issue-key` → open `/studio`, paste key → **Subscribe** (Checkout). After payment, webhooks link `stripe_customer_id`, set `stripe_subscription_id`, and call **`set_tenant_tier`** from the subscription’s price/metadata.

**Tier mapping rules:** For each subscription item’s Price, the worker uses (1) `metadata.tier` if valid, else (2) `STUDIO_STRIPE_PRICE_MAP` / env price ids, else (3) stays conservative (`free` if unknown). **Canceled / unpaid / incomplete_expired** subscriptions downgrade the tenant to **`free`**. **`past_due`** keeps the paid tier until Stripe resolves or cancels (adjust in `stripe_billing.py` if you prefer stricter cutoffs).

**Local testing:** [Stripe CLI](https://stripe.com/docs/stripe-cli) `stripe listen --forward-to localhost:8787/api/studio/billing/webhook` and use the printed **`whsec_…`** as `STRIPE_WEBHOOK_SECRET`.

**Manual override:** `immersive-studio tenants set-tier` still works for support / migrations; the next subscription webhook may overwrite tier until billing state matches.

## Indie / multi-tenant tiers (SaaS mode)

When **`STUDIO_API_AUTH_REQUIRED=1`**, each **workspace** (small studio / customer group) is a **tenant** with:

- **API keys** (hashed in SQLite — only shown once at `tenants issue-key`)
- **Monthly credits** (UTC calendar month), consumed by:
  - `generate-spec`: **1** credit
  - `jobs/run` or **queue enqueue** (sync cost up front): **2** credits, or **6** with **textures**
- **Concurrent job cap** (SQLite counter per tenant while `run_studio_job` is in flight)
- **Texture jobs** blocked on **Free** tier

Tiers are defined in `src/studio_worker/tiers.py` (`free`, `indie`, `team`). **Stripe webhooks** update `tier_id` from the active subscription; **`tenants set-tier`** remains a manual admin override.

**Per-tenant isolation:** job index entries, queue rows, and ad-hoc pack paths are tagged with `tenant_id` so one API key cannot list or download another workspace’s jobs.

Default **without** `STUDIO_API_AUTH_REQUIRED`: single-machine dev — unlimited dev tier, no keys (same as before).

## Blender placeholder mesh

Full pipeline reference (env, CI, Unity): [docs/studio/essentials.md](../../docs/studio/essentials.md).

Exports procedural placeholder geometry as `.glb` from a spec (placeholder until full kitbash lands):

```bash
blender --background --python path/to/site-packages/studio_worker/blender/export_mesh.py -- --spec path/to/spec.json --output path/to/out.glb
```

Use `pack/spec.json` as the `--spec` argument when generating from a worker pack. Requires Blender 4.x on your `PATH`, or set **`STUDIO_BLENDER_BIN`**.

**Integrated path:** `immersive-studio run-job … --export-mesh`, **`POST /api/studio/jobs/run`** / queue with **`export_mesh: true`**, or the **Export placeholder mesh** checkbox on `/studio`. Successful runs place **`Models/<asset_id>/<asset_id>.glb`** and set **`manifest.toolchain.mesh_pipeline`** (`blender:export_mesh.py+ok` or `+error`). Failures are non-fatal: the job still completes with textures/spec; check **`mesh_logs`** in the API response or job metadata.

**Profiles:** `studio_worker/blender/export_mesh.py` picks a coarse shape from **`category`**: `prop` — stacked boxes with deterministic jitter; `environment_piece` — wide platform; `character_base` — two-block silhouette; `material_library` — small swatch cube; other categories fall back to a beveled cube scaled by **`target_height_m`**. PBR material names come from **`studio_worker/pbr_keys.py`** (same ordering as ComfyUI filenames and the Unity importer). The exported glTF material names are **`{variant_id}_{slot_id}`** per part so Unity can match them to **`{base}_Lit`** materials from textures.

## Unity import

Add the UPM package under [`../../packages/studio-unity`](../../packages/studio-unity) to a Unity 2022.3+ **URP** project, then **Immersive Labs → Import Studio Pack...** and select the folder that contains `manifest.json`.

## Layout

| Path | Role |
|------|------|
| `src/studio_worker/` | CLI, API, validation, jobs, ComfyUI client, texture pipeline, Stripe billing |
| `src/studio_worker/billing_config.py` | Env mapping: Stripe Price id → entitlement tier |
| `src/studio_worker/stripe_billing.py` | Webhook handlers, Checkout / Portal session builders |
| `src/studio_worker/billing_routes.py` | FastAPI routes under `/api/studio/billing/*` |
| `studio_worker/comfy_workflows/*.api.json` | ComfyUI `/prompt` graphs (SD1.5 + SDXL albedo v1) |
| `studio_worker/blender/export_mesh.py` | Headless export stub |
| `jobs/`, `queue.sqlite`, `tenants.sqlite`, `packs/…` | Writable state (default **`~/.immersive-studio/worker`** when `STUDIO_REPO_ROOT` is unset; otherwise **`apps/studio-worker/output/`** — gitignored in the monorepo) |

JSON Schema (runtime): `studio_worker/data/studio-asset-spec-v0.1.schema.json` (copy kept in sync with `packages/studio-types/schema/` in the monorepo).

### GPU / Comfy CI smoke test

Opt-in pytest marker `gpu_comfy` runs a minimal SD1.5 txt2img graph against live ComfyUI when:

- `STUDIO_RUN_GPU_COMFY_TESTS=1`
- `STUDIO_COMFY_URL` — base URL of ComfyUI
- `STUDIO_COMFY_CHECKPOINT` — checkpoint **filename** as shown in ComfyUI (SD1.5-style graph)

Optional: `STUDIO_COMFY_STEPS` (default `4`), `STUDIO_COMFY_TIMEOUT_S` (default `420`). Workflow: `.github/workflows/studio-worker-gpu-comfy.yml`.

**GitHub Actions — I can’t set these for you** (they live in your repo/org settings). In GitHub: **Settings → Secrets and variables → Actions → New repository secret**, create:

| Secret | Example value | Purpose |
|--------|----------------|---------|
| `STUDIO_RUN_GPU_COMFY_TESTS` | `1` | Enables the live pytest (otherwise it skips) |
| `STUDIO_COMFY_URL` | `http://127.0.0.1:8188` | Base URL of ComfyUI **as reachable from the workflow runner** |
| `STUDIO_COMFY_CHECKPOINT` | `your_model.safetensors` | Exact checkpoint name in ComfyUI’s loader |

`workflow_dispatch` can override the URL via the **comfy_url** input when non-empty. **GitHub-hosted runners** cannot see your LAN GPU; point `runs-on` at a **self-hosted** runner (or a URL the runner can reach) or run the test locally with the same env vars.
