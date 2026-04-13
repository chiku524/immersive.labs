# Cloudflare Workers, R2, D1, and KV — how they fit Immersive Labs

You already have a **Cloudflare Worker** project and a **Python studio worker** on a VM. Typical production layout: **`api.immersivelabs.space`** → **Worker** (`apps/studio-edge`) → **`ORIGIN_URL`** (e.g. **`https://api-origin.immersivelabs.space`**) → **tunnel** → FastAPI. This doc separates **what can move to the edge today**, what **already exists in code**, and what **would be a larger rewrite**.

---

## 1. Hard constraint: the “studio worker” is not a Workers app

The package in `apps/studio-worker` is **Python + FastAPI**, with:

- **Subprocesses:** Blender, optional ComfyUI / Ollama clients  
- **Long CPU/GPU work** and large on-disk trees under `output/jobs/`  
- **SQLite** (or optional Postgres / Redis / SQS) for queue + tenants  

[**Cloudflare Workers**](https://developers.cloudflare.com/workers/) (V8 isolates) are the wrong runtime for that **core** job: no Blender, no arbitrary long-lived shell pipelines, strict CPU/time limits.

**So:** treat **Workers + KV + D1** as the **edge layer** (routing, auth, cache, small CRUD), and keep **heavy generation** on a **VM, container host, or future Cloudflare Containers** where Python + Blender are viable.

---

## 2. R2 — already supported from the Python worker

Object storage is the easiest “Cloudflare primitive” to adopt **without** rewriting the API.

| Piece | Status |
|--------|--------|
| **S3-compatible uploads** | Implemented: `STUDIO_JOB_ARTIFACTS=r2` uses the same path as `s3` (boto3) with **`STUDIO_S3_ENDPOINT_URL`** pointing at R2. See `scale_config.job_artifacts_backend()` and `job_artifacts.py`. |

**Typical env on the VM** (after creating a bucket + API token in the R2 dashboard):

```bash
STUDIO_JOB_ARTIFACTS=r2
STUDIO_S3_BUCKET=your-bucket-name
STUDIO_S3_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
STUDIO_S3_REGION=auto
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
# optional: STUDIO_S3_KEY_PREFIX=immersive-studio/packs
```

Install the S3 extra: `pip install -e ".[s3]"` (or `".[scale]"`).

**Next steps:** create R2 bucket + token, set env on the Docker/GCE deployment, run one job, confirm the job index exposes a presigned or public URL as today.

---

## 3. KV — good fit for a Worker in front of the API

Use **KV** for data that is **small, eventually consistent, and read-heavy** at the edge:

- Cached **JSON** for `GET /api/studio/health` (short TTL) and **`GET /api/studio/comfy-status`** (shorter TTL; anonymous probe)  
- **Feature flags** or maintenance mode  
- **Rate-limit / abuse** counters (with care: KV is not a strong linearizable DB)

**Pattern:** a **Worker** on **`api.immersivelabs.space`** **`fetch()`s your origin** (tunnel hostname such as **`api-origin`** → Python), then caches parts of the response in KV. You can start with **pass-through** + one cached route to learn bindings.

**Caveat:** the **public `api` hostname** must not be both **tunnel CNAME** and **Worker route** at once — use a **separate origin hostname** (grey CNAME to the tunnel) for **`ORIGIN_URL`**, and point **`api`** at the Worker (proxied DNS + route). See [studio-edge README](../../apps/studio-edge/README.md).

---

## 4. D1 — useful for *new* edge data, not a drop-in for Python’s SQLite

**D1** is SQLite at the edge, but **only inside Workers** (Workers binding). The Python worker’s **`queue.sqlite` / `tenants.sqlite`** are not magically shared with D1.

**Realistic options:**

| Approach | Effort | Notes |
|----------|--------|--------|
| **Keep SQLite/Postgres on the VM** for queue + tenants | None | Current default; optional **`DATABASE_URL`** + Postgres backends already documented. |
| **Postgres as system of record** (Neon, RDS, Hyperdrive) | Medium | Both a **Worker** (via Hyperdrive) and **Python** (direct URL) can talk to the same Postgres; aligns with existing `STUDIO_QUEUE_BACKEND=postgres` / tenants backend. |
| **D1 only for edge-only tables** | Medium | e.g. analytics, edge feature flags, session-ish blobs — **not** the same tables as `queue.sqlite` without sync/replication. |
| **Rewrite queue/tenant logic in TypeScript on Workers** | Large | Only if you explicitly want serverless-first and can give up Python-in-process for those paths. |

**Practical recommendation:** if you want **one shared database** across edge + Python, prefer **Postgres + Hyperdrive** (or plain Postgres URL on the VM) before committing queue rows to D1.

---

## 5. Suggested phases (“migrate *and* move towards”)

**Phase A — Storage (low risk)**  
- Turn on **R2** for `pack.zip` + downloads (`STUDIO_JOB_ARTIFACTS=r2`).  
- Keep API on the VM; UI unchanged except faster/cheaper egress patterns if you later use signed URLs more aggressively.

**Phase B — Edge Worker (medium risk)** — **implemented:** [`apps/studio-edge`](../../apps/studio-edge) (`@immersive/studio-edge`)  
- **Reverse proxy** to `ORIGIN_URL` for all paths.  
- **Optional KV** binding `STUDIO_KV`: short cache for **`GET /api/studio/health`** and **`GET /api/studio/comfy-status`** (`X-Studio-Edge-Cache: HIT|MISS`).  
- **R2** binding `STUDIO_R2` and **D1** binding `STUDIO_D1` are attached for future edge features (schemas/migrations are not applied automatically).  
- From repo root: `npm run dev:studio-edge` / `npm run deploy:studio-edge`.  
- Adjust **DNS / routes** so the **public API hostname** hits the Worker and **`ORIGIN_URL`** uses a **different** hostname that still reaches the tunnel (see [studio-edge README](../../apps/studio-edge/README.md) — avoid fetch loops).

**Phase C — Shared metadata DB (higher effort)**  
- Move queue + tenants to **Postgres**; point Python env at `DATABASE_URL`.  
- Optionally add **Hyperdrive** for Worker read paths.

**Phase D — D1 / KV-only features**  
- New features that are **natively Workers** (short-lived, edge-only) use **D1/KV** without duplicating the Python job engine.

---

## 6. Optional future: Cloudflare Containers / Workers for Platforms

If Cloudflare’s **container** or **longer CPU** offerings become a fit, you could run **parts** of the Python stack closer to R2 — still not a trivial port from the current Dockerfile; treat as a **separate spike** after R2 + edge proxy are stable.

---

## See also

- [essentials.md §1b](./essentials.md) — storage, SQLite, Postgres, Redis, S3/R2  
- [architecture.md § Deployment models](./architecture.md) — static site + API split  
- [apps/studio-worker/README.md](../../apps/studio-worker/README.md) — env table (`STUDIO_JOB_ARTIFACTS`, `STUDIO_S3_*`)  
- [apps/studio-edge/README.md](../../apps/studio-edge/README.md) — Cloudflare Worker proxy + KV health cache
