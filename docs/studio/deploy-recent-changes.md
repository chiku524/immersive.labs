# Deploying recent studio changes (edge, web, worker)

Use this when you have merged **studio-edge**, **web**, or **studio-worker** changes and want production updated.

## 1. Cloudflare Worker (`apps/studio-edge`)

From the monorepo root (requires [Wrangler](https://developers.cloudflare.com/workers/wrangler/) auth, e.g. `wrangler login` or `CLOUDFLARE_API_TOKEN`):

```bash
npm run deploy:studio-edge
```

Or:

```bash
cd apps/studio-edge && npx wrangler deploy
```

**KV:** If `STUDIO_KV` is bound, new routes (e.g. comfy-status cache) apply on deploy. To force clients to miss cache once after a bad entry, delete the key (see [apps/studio-edge/README.md](../../apps/studio-edge/README.md)).

## 2. Marketing / studio UI (`apps/web`)

The site is usually built on **[Vercel](https://vercel.com/)** per root [`vercel.json`](../../vercel.json) (`outputDirectory`: `apps/web/dist`).

**Option A — Git integration:** Push to the branch Vercel watches; it runs `npm install` + `npm run build` at the repo root.

**Option B — CLI (one-time link):** From the repo root:

```bash
npm run build
npx vercel link --scope <your-team-slug>
VERCEL_SCOPE=<your-team-slug> npm run deploy:web
```

**First time from a clone:** create **`.vercel/project.json`** (not committed) with:

```bash
npx vercel link --scope <your-team-slug>
```

After that, **`npm run deploy:web`** runs `scripts/vercel-deploy-prod.mjs`, which:

- Exits early with a clear message if there is **no link and no `VERCEL_TOKEN`**.
- Passes **`--scope`** when **`VERCEL_SCOPE`** or **`VERCEL_TEAM`** is set (multiple teams / non-default scope).
- Passes **`--token`** when **`VERCEL_TOKEN`** is set (CI).

Ensure **production** environment variables include **`VITE_STUDIO_API_URL`** (no trailing slash), e.g. `https://api.immersivelabs.space`.

Examples:

```bash
VERCEL_SCOPE=nico-builds npm run deploy:web
VERCEL_TOKEN=… npm run deploy:web
```

## 3. Python studio worker (`apps/studio-worker`)

There is **no** single “deploy” command for your live API host: you rebuild/restart whatever runs **`immersive-studio serve`** (Docker on a VM, systemd, etc.).

- **GCP + Docker (from your laptop, `gcloud` auth + project set):**  
  **`bash scripts/studio-cloudflare-tunnel/vm-remote-rebuild-studio-worker.sh`**  
  Defaults: **`VM=immersive-studio-worker`**, **`ZONE=us-central1-a`**, project from **`gcloud config`**. Syncs **`/opt/immersive.labs`** to **`origin/main`**, runs **`vm-rebuild-studio-worker.sh`** (Docker rebuild + restart + health). **Push to `main` first.** IAP-only SSH: **`IAP=1 bash …/vm-remote-rebuild-studio-worker.sh`**.
- **GCP + Docker (manual):** follow [deploy-gcp-free-vm.md](./deploy-gcp-free-vm.md) — rebuild image from repo, restart container, confirm `GET /api/studio/health` on the VM and through the tunnel.
- **PyPI:** releasing a new **`immersive-studio`** version uses the repo’s publish workflow / [releasing.md](./releasing.md); production still needs **`pip install -U`** or a new image on the host.

After deploy, confirm **`worker_version`** in `GET https://api…/api/studio/health` matches what you expect.

## Suggested order

1. **Worker** first if the API contract or SQLite queue behavior changed (edge and web depend on correct origin behavior).
2. **studio-edge** so Worker routes, KV caches, and proxy logic match.
3. **Web** last so **`VITE_STUDIO_API_URL`** and UI bundle align with the live API.
