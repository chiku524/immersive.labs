# Apps

| Package | Description |
|---------|-------------|
| `@immersive/web` | Vite + React site (`apps/web`). Marketing site at `/`, **Video Game Generation Studio** at **`/studio`**, docs at **`/docs`**. |
| `@immersive/studio-desktop` | Tauri v2 desktop shell (`apps/studio-desktop`): embeds the Studio UI, local API on `:8787`, optional ComfyUI, auto-update. See [studio-desktop/README.md](./studio-desktop/README.md). |
| `@immersive/studio-edge` | Cloudflare Worker (`apps/studio-edge`): proxy to Python studio API, optional KV cache for `/api/studio/health`, SSE-safe pass-through for queue job events. See [studio-edge/README.md](./studio-edge/README.md). |
| `studio-worker` | PyPI **`immersive-studio`** — CLI + `immersive_studio` SDK (`apps/studio-worker`): Ollama/mock spec generation, JSON Schema validation, Unity pack layout, HTTP API + queue worker. See [studio-worker/README.md](./studio-worker/README.md). |
