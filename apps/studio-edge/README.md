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

## Optional: KV cache for health and comfy-status

1. Create a namespace: `npx wrangler kv namespace create STUDIO_KV`
2. Uncomment `[[kv_namespaces]]` in **`wrangler.toml`** and paste the **`id`**.
3. Redeploy. Responses for **`GET /api/studio/health`** and **`GET /api/studio/comfy-status`** include **`X-Studio-Edge-Cache: HIT`** or **`MISS`**.

Tune health freshness with wrangler var **`HEALTH_CACHE_TTL_MS`** (milliseconds, default `5000`). Health and comfy-status KV writes use **`expirationTtl` ≥ 60s** (Cloudflare KV minimum; comfy used to use ~20s and caused Worker **1101** in production). The edge still treats comfy KV as stale after **~18s** (`COMFY_EDGE_STALE_MS`) so frequent `/studio` polls refresh from origin without waiting for key expiry.

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

2. Set **`ORIGIN_URL`** in **`wrangler.toml`** under **`[vars]`** (checked in for this repo) **or** with **`wrangler secret put ORIGIN_URL`** — **never both** (Cloudflare API error **10053**). If you previously used a secret and want to move to **`[vars]`**, run **`npx wrangler secret delete ORIGIN_URL`** from `apps/studio-edge`, then deploy. For one-off local overrides without editing the file, use **`.dev.vars`** (not committed) or **`npx wrangler dev --var ORIGIN_URL:…`**.

3. **Worker on `api`:** add a **route** for **`api.immersivelabs.space/*`**. DNS for **`api`** should be **proxied** (orange cloud) and must **not** point at the tunnel CNAME (that would bypass the Worker). A common approach is a **proxied** placeholder **A** record (e.g. **`192.0.2.1`**, TEST-NET) so the hostname resolves while traffic is handled by the Worker route.

Exact Cloudflare dashboard steps change over time; keep **one hostname = Worker**, **another = tunnel → origin**.

### Why not `https://api.immersivelabs.space` as `ORIGIN_URL`?

That hostname is already the **Worker’s public URL**. If the Worker proxied to the same host, every `fetch()` to origin would hit **this Worker again**, not the Python process behind the tunnel — a **loop** (or at best useless self-traffic). Use a **different** hostname that goes **straight to FastAPI** (e.g. **`api-origin`** → tunnel).

**`GET /`** on a current **studio-worker** build returns JSON (service name, **`worker_version`**, links to **`/api/studio/health`**, **`/docs`**, etc.). **`GET /favicon.ico`** returns **204** from Python when deployed. If the origin still answers **404** for those paths (older container), **studio-edge** synthesizes **200 JSON** for **`/`** and **204** for **`/favicon.ico`** so **`https://api…/`** is never a bare `{"detail":"Not Found"}` from the edge. Response headers include **`X-Studio-Edge-Synthesized`**. For liveness, still use **`/api/studio/health`**.

### “Gateway or tunnel returned HTML…” (HTTP 5xx from edge)

The Worker turns upstream **HTML error pages** (common for **502 / 503 / 524 / 530**) into JSON so the `/studio` UI can show text instead of `Unexpected token '<'`. That message means **`fetch(ORIGIN_URL)`** got an error page, not FastAPI JSON — usually **tunnel → VM:8787** is down, slow, or **`ORIGIN_URL`** points at the wrong host.

**Checks:** from your laptop, `curl -sS -o /dev/null -w '%{http_code}\n' "$ORIGIN_URL/api/studio/health"` (same URL as in **`wrangler.toml`** or your secret). On the VM or dev PC, from the **monorepo root**: **`bash scripts/studio-cloudflare-tunnel/verify-studio-local.sh`** (Git Bash / Linux / macOS) or **`powershell -File scripts/studio-cloudflare-tunnel/verify-studio-local.ps1`** — they hit Ollama + local FastAPI and print **systemd** or **Windows service** hints for cloudflared when available. **Idempotent `GET /api/studio/*`** requests are **retried briefly** at the edge to ride out transient tunnel blips.

### HTTP **524** (origin timeout) on **`api-origin`**

**524** usually means **Cloudflare’s proxy** (orange cloud on the **`api-origin`** DNS record) gave up waiting for a response from the tunnel/origin chain — often while the Python worker is **busy for a long time** (e.g. slow **Ollama** on a small VM). Mitigations:

1. **DNS only (grey cloud)** for **`api-origin`** — tunnel hostnames often work better **without** the extra proxied hop. Recreate the CNAME with **`CLOUDFLARE_TUNNEL_CNAME_PROXIED=false`** when running **`add-tunnel-cname.sh`**, or turn off proxying in the Cloudflare DNS dashboard for **`api-origin`**.
2. **Python:** the worker uses **Ollama streaming by default** (better read-timeout behavior than blocking mode). Raise **`STUDIO_OLLAMA_READ_TIMEOUT_S`** only if reads are legitimately long; default base when unset is **3000s**, with a second read attempt at ~**1.5×** (capped **14400s**/attempt). Prefer **faster models / more RAM** if generations are slow. If logs show **~900s**, check GCE metadata / Docker env for a pinned **900**.
3. Keep **`/studio`** on the **queued** full-job path (short HTTP requests); avoid any **multi-minute synchronous** API call through **`api`** / **`api-origin`** behind Cloudflare.

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

## Workers.dev / preview URLs show “inactive” in the dashboard

If **only** `routes = [{ pattern = "api.…", zone_name = … }]` is set, deploys often turn off **`*.workers.dev`** and **preview URL** routes unless you opt back in.

This repo sets **`workers_dev = true`** and **`preview_urls = true`** in **`wrangler.toml`**. After changing them, run **`npm run deploy`** (or `npx wrangler deploy`) so Cloudflare picks up the config; the dashboard should then list those routes as active.

Production traffic still uses **`api.immersivelabs.space`** via the zone route; **`immersive-studio-edge.<subdomain>.workers.dev`** is optional for testing the Worker without custom DNS.

## When `api.…` shows an old `worker_version` but the VM is updated

Responses from the Worker include **`X-Studio-Edge-Origin-Host`** (hostname parsed from **`ORIGIN_URL`**, no path or secrets). Use it to confirm the edge is calling the intended origin (usually **`api-origin.immersivelabs.space`**, not **`api.…`** — that would be a fetch loop).

If **`X-Studio-Edge-Origin-Host: api-origin.immersivelabs.space`** but the JSON **`worker_version`** is **older** than `curl http://127.0.0.1:8787/api/studio/health` on the VM:

1. **Same tunnel, multiple connectors** — In [Zero Trust](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels** → your tunnel → **Connectors**, you should see **only** the host that should serve traffic (e.g. the GCE VM). A second laptop or old VM still running **`cloudflared`** with the same tunnel token will receive a share of requests; remove or stop stale connectors.
2. **Remotely managed ingress** — If public hostnames are edited in the dashboard, they can **override** `/etc/cloudflared/config.yml` on the VM. Ensure **`api-origin.immersivelabs.space` → `http://127.0.0.1:8787`** (or the correct connector service) matches what you expect.
3. **KV edge caches** — After fixing origin, purge stale JSON once if needed:  
   - Health: `npx wrangler kv key delete --remote --binding=STUDIO_KV studio:health:v1`  
   - Comfy probe: `npx wrangler kv key delete --remote --binding=STUDIO_KV studio:comfy-status:v1`

**`ORIGIN_URL` secret:** must be the tunnel hostname (e.g. `https://api-origin.immersivelabs.space`), set with:

```bash
printf '%s' 'https://api-origin.immersivelabs.space' | npx wrangler secret put ORIGIN_URL
```

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
