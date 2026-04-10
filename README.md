# immersive.labs

Monorepo for **Immersive Labs**: the public marketing site and planning for the **Video Game Generation Studio** (text → Unity-ready 3D assets).

**Repository landing page:** open [`index.html`](./index.html) in a browser, or serve the repo root as static files (e.g. GitHub Pages), for a short overview with links to both projects.

## Structure

| Path | Description |
|------|-------------|
| `apps/web` | `@immersive/web` — Vite + React application (marketing site + **`/studio`** UI) |
| `apps/studio-edge` | `@immersive/studio-edge` — Cloudflare Worker reverse proxy + optional KV health cache ([README](./apps/studio-edge/README.md)) |
| `apps/studio-worker` | **`immersive-studio`** on PyPI — CLI + Python SDK (`immersive_studio`), spec generation, ComfyUI textures, jobs + zips, HTTP API ([README](./apps/studio-worker/README.md)) |
| `packages/studio-types` | `@immersive/studio-types` — shared types for the studio pipeline |
| `packages/studio-unity` | Unity UPM importer (`com.immersivelabs.studio`) for studio packs |
| `docs/studio` | Planning docs for the video game generation studio |

## Install `immersive-studio` (from PyPI)

The studio worker CLI/SDK is published as **[immersive-studio](https://pypi.org/project/immersive-studio/)**. To install globally with an isolated CLI on `PATH`:

```bash
pipx install immersive-studio
immersive-studio doctor
```

Or in a virtual environment: `pip install immersive-studio`. See [apps/studio-worker/README.md](./apps/studio-worker/README.md) for ComfyUI, Blender, and environment variables. **Contributors** cloning the repo use `pip install -e .` under `apps/studio-worker` — see [CONTRIBUTING.md](./CONTRIBUTING.md).

## Scripts (from repository root)

```bash
npm install
npm run dev
npm run build
npm run preview
# optional: Cloudflare Worker in front of the Python API
npm run dev:studio-edge
```

With the dev server running, open **`http://localhost:5173/studio`** for the studio UI. In another terminal:

```bash
cd apps/studio-worker
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python -m studio_worker.cli serve --host 127.0.0.1 --port 8787
```

Use **mock mode** in the UI if Ollama is not running. Enable **Generate albedo textures** when [ComfyUI](https://github.com/comfyanonymous/ComfyUI) is up and `STUDIO_COMFY_CHECKPOINT` matches a local checkpoint. See [apps/studio-worker/README.md](./apps/studio-worker/README.md) and [packages/studio-unity/README.md](./packages/studio-unity/README.md).

## Studio documentation

**Full platform manual (table of contents, deployment, APIs, scaling, links to all docs):** [docs/studio/platform-manual.md](./docs/studio/platform-manual.md)

**Operational reference (packs, Blender, Unity, CI, env):** [docs/studio/essentials.md](./docs/studio/essentials.md)  

**Deploying the web app (e.g. Vercel):** the UI is static/build output; **SQLite and jobs live on the Python worker host**, not on Vercel — set `VITE_STUDIO_API_URL` to your worker. Details: [docs/studio/essentials.md](./docs/studio/essentials.md) (storage / Vercel subsection).

Planning index: [docs/studio/README.md](./docs/studio/README.md).

## Status

**Phases 1–5 (initial slice)** are implemented: ComfyUI **SD1.5 + SDXL** albedo workflows, persisted **jobs + ZIP downloads**, `/studio` job table, and the **Unity** importer package. See [docs/studio/phased-roadmap.md](./docs/studio/phased-roadmap.md) for remaining hardening (Phase 6) and future mesh/ORM work.
