# API keys and local stack

## Summary

The **default design is local-first**: your new workstation GPU runs image and (where applicable) LLM workloads. **No API keys are required** for that path.

API keys are **optional accelerators** or **quality fallbacks** if local models underperform for structured JSON or reasoning.

## Fully local stack (no API keys)


| Capability                | Tooling                                                            | Notes                                                                   |
| ------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| Structured spec from text | **Ollama**, LM Studio, llama.cpp, vLLM                             | Pick a model strong at JSON; validate output with a schema.             |
| Textures / image passes   | **ComfyUI** + open weights (e.g. SDXL, Flux family where licensed) | Graphs are versioned in repo or sidecar; record model name in manifest. |
| Mesh cleanup / export     | **Blender** (batch/CLI)                                            | Scripting via Python; headless friendly.                                |
| Game engine               | **Unity** (Personal where eligible)                                | No API key for the editor; see Unity’s current plan terms.              |


**You still need:** hardware (GPU), disk for weights, and compliance with each model’s **license** (some weights restrict commercial use or require attribution).

## Optional API keys (hybrid)


| Service type         | Examples                  | When to add                                                                         |
| -------------------- | ------------------------- | ----------------------------------------------------------------------------------- |
| Hosted LLM           | OpenAI, Anthropic, others | Local model JSON is too unreliable after schema + retry tuning.                     |
| Hosted image / 3D    | Various inference APIs    | You want speed without local queue length; **cost** and **data policy** apply.      |
| Version control / CI | GitHub tokens             | Only when automating builds or private repos in CI — not required for local studio. |
| Cloud storage        | R2, S3, GCS               | Only if sharing packs off-machine.                                                  |


**Recommendation:** stay **100% local** until Phase 1 (spec pipeline) is stable; add **one** hosted LLM key only if validation failures block progress.

## Secrets handling (when keys exist)

- Never commit keys; use `.env` (gitignored) or OS secret stores.
- Worker reads env at startup; manifest records **which provider** was used, not the secret.
- For any future multi-user server: per-tenant quotas and prompt logging policies are mandatory — document when that phase is approved.

## Machine prerequisites (checklist)

- NVIDIA (or chosen) GPU drivers installed  
- CUDA / ROCm stack matching ComfyUI and local LLM requirements  
- Blender 4.x LTS installed and on `PATH` for batch mode  
- ComfyUI install location known to the worker config  
- Ollama (or chosen local LLM) installed with a JSON-capable model pulled

Exact versions should be pinned in the worker README when `apps/studio-worker` is added.