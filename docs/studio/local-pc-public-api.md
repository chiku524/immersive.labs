# Local PC as the public Studio API (24/7 without GCE)

Use this when you want **https://immersivelabs.space/studio** (or another public site) to call **your PC** instead of a cloud VM — while keeping ComfyUI, Ollama, Blender, and Tripo on the same machine.

## When this fits

| Approach | Best for |
|----------|----------|
| **Local-only** (`npm run dev` + desktop app) | Solo dev, no public URL needed |
| **PC + Cloudflare Tunnel** (this doc) | Public marketing site + your GPU/CPU at home |
| **GCE VM + tunnel** (`scripts/studio-cloudflare-tunnel/`) | 24/7 API without your PC online |
| **Scale stack** (Postgres + R2 + split worker) | Teams, remote API + local GPU consumer |

## Architecture

```text
Browser (/studio on Vercel)
    → https://api.immersivelabs.space  (Cloudflare Worker, apps/studio-edge)
    → ORIGIN_URL = https://api-origin.immersivelabs.space  (tunnel hostname, DNS-only)
    → cloudflared on your PC
    → http://127.0.0.1:8787  (immersive-studio serve)
```

**Critical:** `ORIGIN_URL` must point at the **tunnel origin hostname**, not the public Worker URL (avoids fetch loops). Keep **api-origin** on **DNS only (grey cloud)**.

## One-time setup on the PC

1. **Bootstrap worker** — `scripts/local-pc-studio/setup-desktop-studio.ps1` or `setup-local-studio.ps1`.
2. **Services** — Ollama, ComfyUI (`start-comfyui-background.ps1`), Studio API (`upgrade-desktop-worker.ps1` or desktop auto-start).
3. **worker.env** — at `%LOCALAPPDATA%\Immersive Studio\worker.env`:
   - `STUDIO_CORS_ORIGINS` includes your public site origins (e.g. `https://immersivelabs.space,https://www.immersivelabs.space`).
   - Tripo, Blender, Comfy URLs as for local jobs.
4. **Cloudflare Tunnel** — install `cloudflared`, create a tunnel, route `api-origin.yourdomain` → `http://127.0.0.1:8787`. See `scripts/studio-cloudflare-tunnel/README.md`.

## Worker / edge configuration

| Variable | Where | Purpose |
|----------|-------|---------|
| `ORIGIN_URL` | `apps/studio-edge` Worker secret | Tunnel origin base URL |
| `STUDIO_CORS_ORIGINS` | `worker.env` | Allow browser calls from public `/studio` |
| `STUDIO_EMBEDDED_QUEUE_WORKER=1` | `worker.env` | Default: API + queue in one process on PC |

Redeploy the edge Worker after changing `ORIGIN_URL`:

```bash
cd apps/studio-edge && npx wrangler deploy
```

## Vercel / web app

Set build-time env so production `/studio` hits the Worker (not localhost):

```env
VITE_STUDIO_API_URL=https://api.immersivelabs.space
```

Local dev can still use `VITE_STUDIO_API_PROXY=1` in `apps/web/.env.development.local`.

## Operations checklist

- [ ] PC stays on (or use wake-on-LAN / UPS) when you need public API.
- [ ] `cloudflared` runs at login (Windows service or Task Scheduler).
- [ ] Desktop app or `upgrade-desktop-worker.ps1` after worker package updates.
- [ ] Monitor `worker-serve.log` and tunnel logs during **502** blips.
- [ ] One small box running Ollama + Comfy + queue often needs tuning: `STUDIO_COMFY_IMAGE_WAIT_S`, `STUDIO_TEXTURE_MAX_SIDE`, `STUDIO_OLLAMA_READ_TIMEOUT_S`, or mock mode for LLM.

## Retiring the cloud VM

When the PC tunnel is stable:

```bash
bash scripts/studio-cloudflare-tunnel/retire-gce-studio-vm.sh
```

Update `ORIGIN_URL` to the PC tunnel hostname before shutting down the VM.

## Related docs

- [scripts/local-pc-studio/README.md](../../scripts/local-pc-studio/README.md) — daily local workflow
- [apps/studio-edge/README.md](../../apps/studio-edge/README.md) — Worker routing and SSE proxy
- [docs/studio/essentials.md](./essentials.md) — env vars and production stability
- [docs/studio/scale-postgres-r2-local-worker.md](./scale-postgres-r2-local-worker.md) — Postgres + R2 when you outgrow SQLite on one PC
