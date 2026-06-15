# Studio: Google Cloud + Cloudflare Tunnel scripts

Operator-focused scripts used with **`docs/studio/deploy-gcp-free-vm.md`**. They assume a small **GCE** VM (often **`e2-micro`**), **Docker** for `immersive-studio-worker`, and **Cloudflare Tunnel** for HTTPS without opening **8787** on the GCP firewall.

## Layout

| File | Purpose |
|------|---------|
| [`gcp-create-e2-vm.sh`](./gcp-create-e2-vm.sh) | On **your laptop** with `gcloud`: create **`e2-micro`** + SSH firewall rule. |
| [`vm-bootstrap-gce-startup.sh`](./vm-bootstrap-gce-startup.sh) | **GCE startup script:** swap, Docker, clone/build image, `docker run` with **`STUDIO_CORS_ORIGINS`** and **`STUDIO_COMFY_URL`** from instance metadata. |
| [`studio-cors-origins.txt`](./studio-cors-origins.txt) | One comma-separated line for **`gcloud --metadata-from-file=STUDIO_CORS_ORIGINS=…`** (commas safe). |
| [`install-comfyui-gce.sh`](./install-comfyui-gce.sh) | **GCE VM (root):** ComfyUI at `/opt/ComfyUI`, CPU PyTorch, SD1.5 checkpoint, **systemd** on `127.0.0.1:8188`. Set metadata **`STUDIO_INSTALL_COMFY=1`** + reboot, or run from **`ensure-comfyui-gce.sh`**. |
| [`ensure-comfyui-gce.sh`](./ensure-comfyui-gce.sh) | **GCE VM (root):** restart **comfyui** service or run install when **`STUDIO_INSTALL_COMFY=1`**. Called from startup fast path. |
| [`install-ollama-debian-vm.sh`](./install-ollama-debian-vm.sh) | Install **Ollama** on the VM host (`OLLAMA_HOST=0.0.0.0`); default pull **`tinyllama`**. **`vm-rebuild`** defaults to Docker **`--network host`** + **`STUDIO_OLLAMA_URL=http://127.0.0.1:11434`**; metadata **`STUDIO_DOCKER_NETWORK=bridge`** restores bridge + port publish. |
| [`cloudflared-service-install.sh`](./cloudflared-service-install.sh) | **`cloudflared service install <token>`** (run as root) for **remotely managed** tunnels. |
| [`cloudflared-config-gce-immersive-api.yml`](./cloudflared-config-gce-immersive-api.yml) | Example **locally managed** named tunnel: **`api-origin.…` → 8787**, **`comfy.…` → 8188**. Match routes in Zero Trust if you use dashboard config instead. |
| [`cloudflared-config.yml.example`](./cloudflared-config.yml.example) | Generic named-tunnel template. |
| [`add-swap-2g.sh`](./add-swap-2g.sh) | 2 GiB swap before heavy `docker build`. |
| [`setup-cloudflare-dns-for-studio.ps1`](./setup-cloudflare-dns-for-studio.ps1) | PowerShell: API DNS helpers (needs **`CLOUDFLARE_API_TOKEN`**). |
| [`setup-cloudflare-vercel-dns.ps1`](./setup-cloudflare-vercel-dns.ps1) | Apex/`www` targets when the zone is on Cloudflare. |
| [`import-zone-to-cloudflare.ps1`](./import-zone-to-cloudflare.ps1) | Onboard a zone to Cloudflare (then change nameservers at registrar). |
| [`verify-studio-public-health.sh`](./verify-studio-public-health.sh) | **Laptop / CI:** DNS + `curl` **`api-origin`** and **`api`** health (read-only). |
| [`verify-studio-local.sh`](./verify-studio-local.sh) | **VM / dev host:** `curl` Ollama + `127.0.0.1:8787` health; **systemd** or **pgrep** cloudflared hint (no systemd required on Windows Git Bash). |
| [`verify-studio-local.ps1`](./verify-studio-local.ps1) | **Windows:** `Invoke-WebRequest` Ollama + local health; **`Get-Service cloudflared`** if installed. |
| [`preflight-studio-public-api.sh`](./preflight-studio-public-api.sh) | **Before UI testing:** remote KV health key delete + 10× `worker_version` sample + tunnel `connections[]` via API (needs `.env`; see repo `.env.example`). |
| [`_cf_api_auth.sh`](./_cf_api_auth.sh) | Sourced helper: `curl` with **Bearer** token or **Global API Key** + email. |
| [`cf-tunnel-admin.sh`](./cf-tunnel-admin.sh) | **CLI tunnel ops:** `verify`, `tunnel-get`, `connector-cleanup <client_id>` (local `cloudflared` + `login` cert), `tunnel-wrangler-info`. |
| [`cf-bootstrap-user-token.sh`](./cf-bootstrap-user-token.sh) | Mint a **User** API token with Tunnel **Read** using **Global API Key** + email (when Account token cannot list connectors). |
| [`push-cloudflared-config-to-gce-vm.sh`](./push-cloudflared-config-to-gce-vm.sh) | **Laptop:** `gcloud compute scp` + `ingress validate` + `systemctl restart cloudflared` on **`immersive-studio-worker`**. |
| [`vm-remote-rebuild-studio-worker.sh`](./vm-remote-rebuild-studio-worker.sh) | **Laptop:** `git fetch` / `reset --hard origin/main` under **`/opt/immersive.labs`** on the VM, then **[`vm-rebuild-studio-worker.sh`](./vm-rebuild-studio-worker.sh)** (Docker rebuild + `docker run` with metadata env). Optional **`IAP=1`** for IAP-only SSH. |
| [`apply-gce-comfy-local-url.sh`](./apply-gce-comfy-local-url.sh) | **Laptop:** set **`STUDIO_COMFY_URL=http://host.docker.internal:8188`** metadata and rebuild (fixes texture `/history` 502 hairpin). Use **`CLEAR_METADATA=1`** to rely on script default only. |
| [`retire-gce-studio-vm.sh`](./retire-gce-studio-vm.sh) | **Laptop:** delete **`immersive-studio-worker`** when moving to local-only Studio (`RETIRE_CONFIRM=1` skips prompt). |
| [`vm-check-studio-stack.sh`](./vm-check-studio-stack.sh) | **GCE VM (SSH):** `cloudflared`, `docker`, `127.0.0.1:8787` health, **Blender** in `studio-worker` container. |
| [`vm-recover-tunnel-and-docker.sh`](./vm-recover-tunnel-and-docker.sh) | **GCE VM (browser SSH):** restart Docker + `cloudflared`, print public health curl hints (fixes HTTP **530**). |
| [`vm-remote-recover-tunnel-light.sh`](./vm-remote-recover-tunnel-light.sh) | **Laptop:** refresh startup script + **reset VM** (fast path, no docker rebuild) — first choice for HTTP **530**. |
| [`vm-remote-recover-production.sh`](./vm-remote-recover-production.sh) | **Laptop:** metadata + reset + **full** git pull + docker rebuild (use when light recover fails). |
| [`studio-stack-watchdog.sh`](./studio-stack-watchdog.sh) | **GCE VM (root/systemd):** every 5 min — restart Docker/cloudflared/Comfy if unhealthy; reboot after 3 failed network/tunnel checks. |
| [`install-studio-watchdog-gce.sh`](./install-studio-watchdog-gce.sh) | Install **`studio-stack-watchdog.timer`** on the VM (auto-run from bootstrap fast path). |
| [`diagnose-tunnel-status.sh`](./diagnose-tunnel-status.sh) | **Laptop:** Cloudflare tunnel connector count + public health probes (needs repo `.env`). |
| [`cloudflared-connector-immersive-labs-studio-api.template.yml`](./cloudflared-connector-immersive-labs-studio-api.template.yml) | **Named tunnel ingress:** `api-origin` → `8787`, `comfy` → `8188`. Copy to the connector host; set `credentials-file` path; run `cloudflared tunnel run`. |
| [`gce-ssh-immersive-studio-worker.ps1`](./gce-ssh-immersive-studio-worker.ps1) | **Windows:** IAP SSH using **OpenSSH** instead of PuTTY (`CLOUDSDK_COMPUTE_SSH_WITH_NATIVE_OPENSSH=1`). |

**Tunnel had no connectors (HTTP 530):** start `cloudflared` on a host that can reach `127.0.0.1:8787` (VM with Docker, or your dev PC while testing). A working Windows example lives at `%USERPROFILE%\.cloudflared\immersive-labs-studio-api-connector.yml` after you copy the template and point `credentials-file` at your `52513248-….json`.

### Why HTTP 530 keeps coming back (VM does **not** sleep)

**GCE `e2-micro` instances do not sleep** like a laptop — they run until stopped, preempted, or rebooted. HTTP **530** / error **1033** means Cloudflare has **zero active tunnel connectors**, not that the VM powered off.

Common causes on a small always-on VM:

| Cause | What you see | Fix |
|-------|----------------|-----|
| **Host network hung** | Serial log: `network is unreachable`, metadata server errors, cloudflared QUIC failures | **Reset VM** (`vm-remote-recover-tunnel-light.sh`) — reboot restores NIC |
| **cloudflared crashed / stuck** | Tunnel 0 connectors; local `:8787` may still work | `systemctl restart cloudflared` or light recover |
| **Docker / studio-worker stopped** | Origin 502/530; tunnel up but origin refused | `docker start studio-worker` or recover script |
| **OOM on 1 GiB RAM** | Random service death (Comfy + Docker + cloudflared) | Swap (bootstrap adds 2 GiB), avoid heavy concurrent jobs, watchdog restarts stack |
| **Startup script only runs on boot** | Services died mid-uptime; no auto-heal until reboot | **`studio-stack-watchdog.timer`** (installed by bootstrap) |

**First response from your laptop:** `bash scripts/studio-cloudflare-tunnel/vm-remote-recover-tunnel-light.sh`  
**If still broken:** `bash scripts/studio-cloudflare-tunnel/vm-remote-recover-production.sh` (full rebuild).

**Stray connector you cannot SSH to:** `cloudflared tunnel cleanup --connector-id …` only drops sessions until the process reconnects. To invalidate old credentials everywhere, **rotate** the tunnel secret: `PATCH …/cfd_tunnel/{tunnel_id}` with a new `tunnel_secret` (base64 of 32 random bytes), rebuild the credentials JSON (`AccountTag`, `TunnelID`, `TunnelSecret`, optional `Endpoint: ""`), **`gcloud compute scp`** to `/etc/cloudflared/52513248-….json` on **`immersive-studio-worker`**, then **`sudo systemctl restart cloudflared`**. Requires **Cloudflare Tunnel Edit** on the API token. Then **`cf-tunnel-admin.sh connector-cleanup`** if a stale `client_id` still appears, and **`wrangler kv key delete studio:health:v1`** (remote) for a fresh edge health cache.

## IAP SSH (PuTTY “Remote side unexpectedly closed”, or `start-iap-tunnel` 4003)

Prerequisites (CLI, project **`immersive-labs-studio`**):

1. **Enable APIs:** `gcloud services enable iap.googleapis.com networkmanagement.googleapis.com --project=immersive-labs-studio`
2. **Firewall from IAP to port 22:** allow **`35.235.240.0/20`** → **`tcp:22`** to instances with the same **network tag** as the VM (e.g. `immersive-studio-ssh`). Example rule name: `allow-iap-ssh-immersive-studio`.
3. **Verify reachability:**  
   `printf "Y\n" | gcloud compute ssh immersive-studio-worker --zone=us-central1-a --project=immersive-labs-studio --tunnel-through-iap --troubleshoot`  
   You want **Connectivity Test … REACHABLE** from an IAP source IP to the VM internal IP on port 22.

**Windows / PuTTY:** `gcloud` defaults to **plink**. Set a **user** environment variable **`CLOUDSDK_COMPUTE_SSH_WITH_NATIVE_OPENSSH=1`**, close all terminals, reopen, then SSH again. Or run:

`powershell -ExecutionPolicy Bypass -File scripts/studio-cloudflare-tunnel/gce-ssh-immersive-studio-worker.ps1`

**Browser SSH:** In Cloud Console → Compute Engine → VM → **SSH** drop-down → **Open in browser window** (does not use local PuTTY).

**NumPy warning:** optional speed-up for IAP connectivity checks — install NumPy into the Cloud SDK **bundled** Python (path varies); the warning is safe to ignore.

## Environment: worker + ComfyUI

- **`STUDIO_CORS_ORIGINS`** — Set on the **running container** (and in metadata for the startup script). Every browser origin for `/studio` must match **exactly** (scheme + host).
- **Ollama (optional metadata / `docker -e`)** — From **`immersive-studio` 0.1.9+**, defaults are a **600s** base read timeout (when unset), **8s** connect timeout, and **preflight + model verify** enabled. **`vm-bootstrap-gce-startup.sh`** / **`vm-rebuild-studio-worker.sh`** pass **`STUDIO_OLLAMA_READ_TIMEOUT_S`** through instance metadata when set (omit metadata to use worker defaults). You can also set **`STUDIO_OLLAMA_DISABLED`**, **`STUDIO_OLLAMA_CONNECT_TIMEOUT_S`**, **`STUDIO_OLLAMA_PREFLIGHT`**, **`STUDIO_OLLAMA_VERIFY_MODEL`**, **`STUDIO_OLLAMA_URL`**, **`STUDIO_OLLAMA_MODEL`** on the container — see **`docs/studio/deploy-gcp-free-vm.md`** and **`apps/studio-worker/README.md`**.
- **`STUDIO_COMFY_URL`** — Base URL for ComfyUI’s HTTP API **as seen from the worker process**.
  - **Worker in Docker, ComfyUI on the VM host (recommended):** **`http://host.docker.internal:8188`** with `docker run --add-host=host.docker.internal:host-gateway`. This is the **default** in `vm-rebuild-studio-worker.sh` / `vm-bootstrap-gce-startup.sh` when metadata is unset — avoids polling `/history` through **`https://comfy.immersivelabs.space`** while Comfy is busy on the same VM.
  - **Worker `--network host` on the VM:** default **`http://127.0.0.1:8188`**.
  - **Public tunnel URL:** use **`https://comfy.immersivelabs.space`** only when ComfyUI runs on **another** machine, or for browser/`curl` checks — not for same-VM Docker workers.
  - **ComfyUI on another host:** set metadata to that host’s HTTPS URL.
- **Tunnel public hostnames** — Typically **`api-origin`** (or your API hostname) → **`http://127.0.0.1:8787`**, and optionally **`comfy`** → **`http://127.0.0.1:8188`**. Use the Cloudflare account that owns **`immersivelabs.space`** (or your zone) when creating DNS routes; `cloudflared tunnel route dns` uses the CLI login’s default zone.

## DNS: `cloudflared tunnel route dns` picks the wrong zone

If you have **multiple** Cloudflare accounts or zones, `cloudflared tunnel route dns <id> comfy.immersivelabs.space` may create **`comfy.immersivelabs.space.your-other-zone.net`** (wrong zone) instead of a record under **`immersivelabs.space`**.

**Fix (recommended):** use the Cloudflare **API** with a token scoped to **`immersivelabs.space`** (Zone → DNS → Edit):

**PowerShell** (from repo root; reuses the same tunnel id as `api`):

```powershell
$env:CLOUDFLARE_API_TOKEN = '<Zone DNS Edit token>'
.\scripts\studio-cloudflare-tunnel\setup-cloudflare-dns-for-studio.ps1 -ApiHost comfy
```

**Bash** (Git Bash / Linux; same token):

```bash
export CLOUDFLARE_API_TOKEN='...'
bash scripts/studio-cloudflare-tunnel/add-tunnel-cname.sh comfy 52513248-a776-4f3d-b6fb-7e17c3858b2b immersivelabs.space
```

Then confirm: `nslookup comfy.immersivelabs.space` (should resolve via Cloudflare). In **Zero Trust → Tunnels → your tunnel → Public hostnames**, add **`comfy.immersivelabs.space` → `http://127.0.0.1:8188`** if not already present (must match `cloudflared` ingress on the VM).

**`curl -I https://comfy.immersivelabs.space/system_stats` returns HTTP 530** — Cloudflare could not reach the origin. On the VM (or host that should answer Comfy): `sudo systemctl status cloudflared` (or your install method), confirm the tunnel is **healthy** in Zero Trust → Tunnels, and that **ComfyUI is running** and bound to **`127.0.0.1:8188`** so the tunnel’s `http://127.0.0.1:8188` target is not connection-refused.

Remove any mistaken **`comfy`** record under the **wrong** zone (e.g. `boing.network`) in the DNS dashboard if a bad `cloudflared tunnel route dns` run created it.

## Related

- Runbook: [`docs/studio/deploy-gcp-free-vm.md`](../../docs/studio/deploy-gcp-free-vm.md)
- Edge Worker + origin: [`apps/studio-edge/README.md`](../../apps/studio-edge/README.md)
- Web hub: **`/docs`** on the marketing site (`apps/web`)
