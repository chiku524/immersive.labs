# Host Studio on your local PC (ComfyUI + Blender + API)

**Local-first (recommended):** run the full pipeline on **your PC** with GPU/CPU. The GCE VM is optional — only needed for 24/7 public `api.immersivelabs.space` without your machine online.

## Bootstrap once

```powershell
# From monorepo root (Windows)
.\scripts\local-pc-studio\setup-local-studio.ps1
```

Git Bash / macOS / Linux:

```bash
bash scripts/local-pc-studio/setup-local-studio.sh
```

**Docker API** (Comfy still on host for GPU): add `-UseDocker` / `--docker`, then use `start-studio-api-docker.ps1` or `docker compose -f scripts/local-pc-studio/docker-compose.local.yml up --build`.

## Every session

| Step | Command |
|------|---------|
| ComfyUI (textures) | `.\scripts\local-pc-studio\start-comfyui.ps1` — use `COMFYUI_USE_GPU=1` when CUDA PyTorch is installed |
| Studio API | `.\scripts\local-pc-studio\start-studio-api.ps1` **or** Docker compose above |
| Web `/studio` | `npm run dev` → http://localhost:5173/studio (Vite proxies `/api/studio` → `:8787`) |

## Retire the GCE VM

When you no longer need cloud-hosted API:

```bash
bash scripts/studio-cloudflare-tunnel/retire-gce-studio-vm.sh
```

Public **https://immersivelabs.space/studio** will show worker errors until you either use **local dev** only, or run **Cloudflare Tunnel** from your PC and update Worker `ORIGIN_URL` (see [Optional: expose your PC](#optional-expose-your-pc-to-the-browser)).

---

## Quick start today (mock + mesh, no cloud)

Prove the pipeline end-to-end before fixing production tunnels or paying for text-to-3D APIs:

```powershell
# Once: venv + editable install
python -m venv apps/studio-worker/.venv
apps\studio-worker\.venv\Scripts\pip install -e "apps/studio-worker[dev]"

# Generate pack.zip with mock spec + Blender placeholder GLB (needs Blender on PATH)
.\scripts\local-pc-studio\smoke-mock-mesh-pack.ps1
```

Git Bash / macOS / Linux: `bash scripts/local-pc-studio/smoke-mock-mesh-pack.sh`

Then in Unity: **Immersive Labs → Import Studio Pack…** → pick the job folder under `apps/studio-worker/output/jobs/` (see [packages/studio-unity/README.md](../../packages/studio-unity/README.md)).

**When you have Tripo credits:** in `apps/studio-worker/.env.local` set `STUDIO_MESH_PROVIDER=tripo` and `STUDIO_TRIPO_API_KEY=…`, then re-run the smoke script or `/studio` with **Export mesh** checked.

---

**Production scale path (Neon Postgres + R2 + remote API):** run only the queue worker on this PC — see [docs/studio/scale-postgres-r2-local-worker.md](../../docs/studio/scale-postgres-r2-local-worker.md) and `bash scripts/studio-scale/run-local-queue-worker.sh`. Use the Comfy start scripts below; skip `start-studio-api` if the API runs on GCP.

---

Use this layout when **your machine** runs the full **SQLite** stack: **ComfyUI** (textures), **Blender** (mesh), and **`immersive-studio serve`** (HTTP API + embedded queue). The marketing site can stay on Vercel while `/studio` talks to your PC (see [Expose to the internet](#optional-expose-your-pc-to-the-browser)).

## Prerequisites

- **Python 3.11+** and **Node.js** (for `apps/web`).
- **ComfyUI** with its HTTP API (default in many installs: `http://127.0.0.1:8188`).
- **Blender 4.x** on `PATH`, or set `STUDIO_BLENDER_BIN` to `blender.exe` (Windows) or `blender` (macOS/Linux).
- **Ollama**: required when **Mock** is off in `/studio` and **`STUDIO_OLLAMA_DISABLED`** is not set on the worker (default is off in dev). Install from [ollama.com](https://ollama.com) or `winget install Ollama.Ollama`, then `ollama pull llama3.2` (matches worker default `STUDIO_OLLAMA_MODEL`). Set `STUDIO_OLLAMA_URL` / `STUDIO_OLLAMA_MODEL` in `apps/studio-worker/.env.local` if needed. From **0.1.9**, the worker preflights **`GET /api/tags`** before each LLM call and checks the model is installed unless you disable preflight/verify via env (see `apps/studio-worker/.env.example`). For a PC without Ollama, set **`STUDIO_OLLAMA_DISABLED=1`** so full jobs still complete with mock specs.

## 1. Install the studio worker (editable)

From the **monorepo root** (recommended venv path `apps/studio-worker/.venv`, already gitignored):

```bash
python -m venv apps/studio-worker/.venv
# Windows Git Bash:  source apps/studio-worker/.venv/Scripts/activate
# Windows cmd:        apps\studio-worker\.venv\Scripts\activate.bat
# macOS/Linux:        source apps/studio-worker/.venv/bin/activate
pip install -e "apps/studio-worker[dev]"
```

The `start-studio-api` scripts prefer `apps/studio-worker/.venv` when present.

## 2. Worker environment (`apps/studio-worker/.env.local`)

Copy the template and edit paths for **your** machine:

```bash
cp scripts/local-pc-studio/env.studio-worker.local.template apps/studio-worker/.env.local
```

Set at least:

| Variable | Purpose |
|----------|---------|
| `STUDIO_REPO_ROOT` | Absolute path to this monorepo root (jobs + SQLite live under `apps/studio-worker/output`). |
| `STUDIO_COMFY_URL` | `http://127.0.0.1:8188` when Comfy runs on the same PC. |
| `STUDIO_CORS_ORIGINS` | Required if the web app calls `http://127.0.0.1:8787` **directly** (see §4). |
| `STUDIO_BLENDER_BIN` | Full path to Blender if not on `PATH` (common on Windows). |

`apps/studio-worker/.env.local` is gitignored (`*.local`). The start scripts load it on Windows (PowerShell) or you can `export` / `set` vars manually.

## 3. Start ComfyUI

The Studio worker only **checks** Comfy; it does **not** start it. If `/studio` shows **“actively refused”** / **WinError 10061** on `http://127.0.0.1:8188`, nothing is listening on that port yet.

### Install (once)

Clone [ComfyUI](https://github.com/comfyanonymous/ComfyUI) somewhere outside this monorepo (e.g. `C:\src\ComfyUI`), create a venv there, install its `requirements.txt`, and download a checkpoint into `models/checkpoints/` (see Comfy’s README).

### Run (every session)

**Easiest — helper script from the monorepo root** (expects a sibling folder `../ComfyUI` with `.venv`, or set `COMFYUI_ROOT`):

```powershell
.\scripts\local-pc-studio\start-comfyui.ps1
```

```bash
bash scripts/local-pc-studio/start-comfyui.sh
```

By default the script passes **`--cpu`**, which is required when PyTorch is the **CPU-only** wheel (`2.x+cpu`). If you install **CUDA** PyTorch and have a working GPU stack, run with `COMFYUI_USE_GPU=1` so `--cpu` is omitted.

Or manually from your **ComfyUI** folder (not `immersive.labs`):

```powershell
.\.venv\Scripts\activate
python main.py --listen 127.0.0.1 --port 8188 --cpu
```

Use **Python 3.12** for Comfy’s venv if possible — **3.14** often lacks prebuilt `torch` wheels yet.

Wait until the terminal prints something like **“To see the GUI go to: http://127.0.0.1:8188”**. Leave this window open.

### Verify

In another terminal:

```bash
curl -sS http://127.0.0.1:8188/system_stats
```

Or open `http://127.0.0.1:8188` in a browser — you should see the Comfy UI.

### Without local Comfy (textures via cloud)

If you do **not** want to run Comfy on this PC, set in `apps/studio-worker/.env.local`:

```env
STUDIO_COMFY_URL=https://comfy.immersivelabs.space
```

Then restart `immersive-studio serve`. The worker calls **`/system_stats`** over HTTPS; if `/studio` shows **“returned HTML … not ComfyUI JSON”**, the hostname is serving a **Cloudflare/gateway error or challenge page** (tunnel down, WAF, or Comfy not actually exposed on that path) — fix the **remote** tunnel/DNS, or run Comfy locally again. The worker sends a normal browser **User-Agent** so basic bot blocks are avoided.

## 4. Start the Studio API

**Windows (PowerShell), from repo root:**

```powershell
.\scripts\local-pc-studio\start-studio-api.ps1
```

**macOS / Linux / Git Bash, from repo root:**

```bash
bash scripts/local-pc-studio/start-studio-api.sh
```

This sets `STUDIO_REPO_ROOT`, loads `apps/studio-worker/.env.local` if present, and runs `immersive-studio serve --host 127.0.0.1 --port 8787`.

Smoke test:

```bash
curl -sS http://127.0.0.1:8787/api/studio/health
```

## 5. Start the web app (`/studio`)

**Option A — Vite proxy (recommended):** same-origin requests, no CORS setup for `localhost` ↔ `127.0.0.1`.

1. Create `apps/web/.env.development.local` with:

   ```env
   VITE_STUDIO_API_PROXY=1
   ```

2. From repo root: `npm install` (once), then `npm run dev`.

Open `/studio`. The UI hits `/api/studio/...` on the Vite dev server; Vite forwards to `http://127.0.0.1:8787`.

**Option B — Direct API URL:** in `apps/web/.env.development.local` set:

```env
VITE_STUDIO_API_URL=http://127.0.0.1:8787
```

Then set **`STUDIO_CORS_ORIGINS`** on the worker to include your dev origin, e.g.:

`http://127.0.0.1:5173,http://localhost:5173`

## Migrating off cloud workers

1. **Bootstrap local:** `setup-local-studio.ps1` / `.sh` (creates `.env.local` + Vite proxy).
2. **Retire VM:** `bash scripts/studio-cloudflare-tunnel/retire-gce-studio-vm.sh` (stops GCP billing).
3. **Use `/studio` locally:** `npm run dev` — do not rely on `VITE_STUDIO_API_URL=https://api.immersivelabs.space` in dev (proxy mode overrides it).
4. **Production site:** Vercel builds still point at the public Worker until you change env or add a PC tunnel. For personal use, local dev is enough.

## Optional: expose your PC to the browser

If you want **https://immersivelabs.space/studio** (or another public origin) to call APIs on your PC:

1. Run **Cloudflare Tunnel** (or **Tailscale Funnel**, **ngrok**, etc.) on this machine so a public hostname forwards to `http://127.0.0.1:8787`.
2. Set **Vercel** `VITE_STUDIO_API_URL` to that HTTPS origin at build time.
3. Set **`STUDIO_CORS_ORIGINS`** on your local `immersive-studio serve` to include `https://www.immersivelabs.space` (and apex) so the browser is allowed to call your tunnel host.

See `scripts/studio-cloudflare-tunnel/README.md` for tunnel patterns used elsewhere in this repo.

## Optional: separate queue process

Default **embedded** SQLite consumer runs inside `serve`. To use a **dedicated** consumer instead:

```bash
set STUDIO_EMBEDDED_QUEUE_WORKER=0
immersive-studio queue-worker
```

(Second terminal; same `.env.local` / repo root.)

## Troubleshooting

| Symptom | Check |
|--------|--------|
| **WinError 10061** / **connection refused** on `127.0.0.1:8188` | ComfyUI is not running — see **§3 Start ComfyUI** (separate terminal). |
| **`Torch not compiled with CUDA enabled`** on startup | You installed **CPU-only** PyTorch; start Comfy with **`--cpu`** (the `start-comfyui` scripts do this by default) or reinstall PyTorch with CUDA. |
| **`OSError: [Errno 22] Invalid argument`** in KSampler / `tqdm` / `stderr.flush` (Windows) | Often a **broken or non-console stderr** (IDE terminal, detached process). The `start-comfyui` scripts set **`TQDM_DISABLE=1`** so Comfy skips tqdm progress bars. Or run Comfy from **cmd.exe** / **PowerShell** in its own window; restart Comfy after changing env. |
| Textures fail | Comfy URL, checkpoint names, `STUDIO_COMFY_PROFILE` / `STUDIO_COMFY_CHECKPOINT` in `.env.local`. |
| Mesh / GLB fails | `immersive-studio doctor --strict` and `STUDIO_BLENDER_BIN`. |
| CORS errors | Use **Option A** (proxy) or expand `STUDIO_CORS_ORIGINS`. |
| 502 from Ollama | Start Ollama or turn **Mock** on in `/studio`. |
| Worker in **WSL**, Comfy on **Windows** | `127.0.0.1` inside WSL is not your Windows host — use the Windows host IP from WSL (`/etc/resolv.conf` nameserver) or run Comfy inside WSL too. |
