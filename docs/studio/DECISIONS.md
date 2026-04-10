# Phase 0 decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| First asset category | `prop` | Smallest scope for mesh + collider + textures. |
| First style preset (implementation order) | `toon_bold` | Faster shader validation; lower texture resolution defaults. |
| Studio worker language | Python | Blender batch automation and ML ecosystem; matches [architecture.md](./architecture.md). |
| Unity reference pipeline | **URP** | Default for new Unity projects; documented in pack templates. |
| Local LLM default | Ollama at `http://127.0.0.1:11434` | No API key; configurable via env / CLI. |

Subsequent presets (`anime_stylized`, `realistic_hd_pbr`) reuse the same schema and validator with different limits and prompts.
