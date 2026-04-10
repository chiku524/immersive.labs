# Apps

| Package | Description |
|---------|-------------|
| `@immersive/web` | Vite + React site (`apps/web`). Marketing site at `/` and **Video Game Generation Studio** UI at **`/studio`**. |
| `@immersive/studio-edge` | Cloudflare Worker (`apps/studio-edge`): proxy to Python studio API, optional KV cache for `/api/studio/health`. See [studio-edge/README.md](./studio-edge/README.md). |
| `studio-worker` | PyPI **`immersive-studio`** — CLI + `immersive_studio` SDK (`apps/studio-worker`): Ollama/mock spec generation, JSON Schema validation, Unity pack layout, HTTP API. See [studio-worker/README.md](./studio-worker/README.md). |
