## Learned User Preferences

- Often asks to commit and push completed work to GitHub when ready.
- Prefers deploy and cloud steps to be run via CLI and terminal scripts (for example gcloud and VM rebuild helpers), not only described in chat.
- Expects documentation to stay current and wants a clear, semantic docs area on the public website for end users.
- When given an ordered list of recommendations, prefers they be implemented in that same order.
- Wants job failure information emphasized in the UI (for example last_error) and concrete changes that improve success rate, not only clearer messaging.
- Interested in SSE or WebSocket job updates as a UX improvement alongside or beyond polling.
- Wants the studio worker exposed as a normal pip-installable CLI (immersive-studio on PyPI) so others can run it from their own machines.
- Provides detailed iterative feedback on branding, logos, social images, typography, and abstract visual motifs for marketing assets.

## Learned Workspace Facts

- immersive.labs is a monorepo with npm workspaces for apps such as web and studio-edge, plus a Python studio-worker under apps/studio-worker.
- Production Studio uses a Cloudflare Worker in front of a Cloudflare-tunneled API origin; ORIGIN_URL for the edge Worker must point at the tunnel origin hostname, not the public Worker URL.
- Full Studio jobs may use Ollama, ComfyUI, and optional Blender mesh export; running all of that on one small VM often correlates with Ollama read timeouts and intermittent tunnel or origin HTTP 502 responses under load.
- ComfyUI is reached using STUDIO_COMFY_URL to the service base URL; Blender needs an install or STUDIO_BLENDER_BIN set to the executable.
- Recurring ops guidance includes keeping the tunnel API hostname DNS-only where recommended, monitoring cloudflared and app logs during 502s, and tuning Ollama via model size, RAM or swap, mock mode, or STUDIO_OLLAMA_READ_TIMEOUT_S with the tradeoff that long timeouts occupy the queue worker.
- Typical deploy targets include Wrangler for studio-edge, Vercel for web, and GCP or Docker-based flows for studio-worker, including scripts under scripts/studio-cloudflare-tunnel for remote VM rebuilds.
- The immersive-studio Python package is published to PyPI with GitHub Actions workflows for builds and releases.
