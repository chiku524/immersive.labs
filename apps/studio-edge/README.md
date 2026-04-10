# `@immersive/studio-edge`

Cloudflare **Worker** that **reverse-proxies** to the Python **studio worker** (`apps/studio-worker`) and optionally caches **`GET /api/studio/health`** in **KV**.

This does **not** replace the Python API — it sits in front of it when you wire DNS/routes in Cloudflare.

## Prerequisites

- Node 20+ recommended  
- Cloudflare account + `wrangler login`  
- Python worker reachable at **`ORIGIN_URL`** (local Docker, tunnel hostname, etc.)

## Install

From monorepo root:

```bash
npm install
```

## Local dev

With the studio worker on **`http://127.0.0.1:8787`**:

```bash
cd apps/studio-edge
npm run dev
```

Wrangler prints a `*.workers.dev` URL — open paths like `/api/studio/health` there; they proxy to `ORIGIN_URL`.

Override origin for one run:

```bash
npx wrangler dev --var ORIGIN_URL:https://api.example.com
```

## Optional: KV cache for health

1. Create a namespace: `npx wrangler kv namespace create STUDIO_KV`
2. Uncomment `[[kv_namespaces]]` in **`wrangler.toml`** and paste the **`id`**.
3. Redeploy. Responses for **`GET /api/studio/health`** include **`X-Studio-Edge-Cache: HIT`** or **`MISS`**.

Tune freshness with wrangler var **`HEALTH_CACHE_TTL_MS`** (milliseconds, default `5000`). KV entries expire after **60s** (`expirationTtl`).

## Production routing (avoid a fetch loop)

If the Worker is bound to **`https://api.immersivelabs.space`**, **`ORIGIN_URL` must not** be the same hostname (the Worker would call itself).

Recommended pattern:

1. **Tunnel → Python only on `api-origin`.** In **`/etc/cloudflared/config.yml`** on the VM, expose **`api-origin.immersivelabs.space`** (not `api`) to `http://127.0.0.1:8787`. The checked-in example is **`scripts/studio-cloudflare-tunnel/cloudflared-config-gce-immersive-api.yml`**:

   ```yaml
   ingress:
     - hostname: api-origin.immersivelabs.space
       service: http://127.0.0.1:8787
     - service: http_status:404
   ```

   Create **DNS only** (grey cloud) CNAME **`api-origin`** → **`<tunnel-id>.cfargotunnel.com`**.

2. Set **`ORIGIN_URL`** with **`wrangler secret put ORIGIN_URL`** to **`https://api-origin.immersivelabs.space`**. For local dev, use **`.dev.vars`** (not committed); do **not** put `ORIGIN_URL` in **`[vars]`** in `wrangler.toml` for production — a plain `[vars]` binding blocks the same-named secret (API error **10053**); deploy without it, then set the secret.

3. **Worker on `api`:** add a **route** for **`api.immersivelabs.space/*`**. DNS for **`api`** should be **proxied** (orange cloud) and must **not** point at the tunnel CNAME (that would bypass the Worker). A common approach is a **proxied** placeholder **A** record (e.g. **`192.0.2.1`**, TEST-NET) so the hostname resolves while traffic is handled by the Worker route.

Exact Cloudflare dashboard steps change over time; keep **one hostname = Worker**, **another = tunnel → origin**.

### Why not `https://api.immersivelabs.space` as `ORIGIN_URL`?

That hostname is already the **Worker’s public URL**. If the Worker proxied to the same host, every `fetch()` to origin would hit **this Worker again**, not the Python process behind the tunnel — a **loop** (or at best useless self-traffic). Use a **different** hostname that goes **straight to FastAPI** (e.g. **`api-origin`** → tunnel).

Seeing **`{"detail":"Not Found"}`** on **`https://api.immersivelabs.space/`** (trailing slash, root path) is normal: the FastAPI app may not define **`GET /`**; try **`/api/studio/health`** instead.

## R2 and D1 on this Worker

Production bindings (see **`wrangler.toml`**):

| Binding     | Resource |
|------------|----------|
| **`STUDIO_R2`** | Bucket **`immersive-studio-edge-r2`** |
| **`STUDIO_D1`** | Database **`immersive-studio-edge-meta`** (`database_id` in `wrangler.toml`) |

Job artifacts uploaded by **Python** can still use **S3-compatible R2** via env on the VM (`STUDIO_JOB_ARTIFACTS=r2`, …). The Worker bucket is for **edge-native** use (e.g. future signed URLs, small blobs) and is **not** automatically the same bucket as Python unless you point both at the same `bucket_name`.

Create replacements locally with:

```bash
npx wrangler r2 bucket create <bucket-name>
npx wrangler d1 create <database-name>
```

Then update **`wrangler.toml`** and redeploy.

## Deploy

```bash
cd apps/studio-edge
npm run deploy
```

Set secrets in production (do not commit):

```bash
npx wrangler secret put ORIGIN_URL
# paste https://api-origin.immersivelabs.space
```

## Scripts (monorepo root)

```bash
npm run dev -w @immersive/studio-edge
npm run deploy -w @immersive/studio-edge
```

## See also

- [docs/studio/cloudflare-edge-and-storage.md](../../docs/studio/cloudflare-edge-and-storage.md)
