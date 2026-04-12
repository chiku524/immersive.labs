# Studio: Google Cloud + Cloudflare Tunnel scripts

Operator-focused scripts used with **`docs/studio/deploy-gcp-free-vm.md`**. They assume a small **GCE** VM (often **`e2-micro`**), **Docker** for `immersive-studio-worker`, and **Cloudflare Tunnel** for HTTPS without opening **8787** on the GCP firewall.

## Layout

| File | Purpose |
|------|---------|
| [`gcp-create-e2-vm.sh`](./gcp-create-e2-vm.sh) | On **your laptop** with `gcloud`: create **`e2-micro`** + SSH firewall rule. |
| [`vm-bootstrap-gce-startup.sh`](./vm-bootstrap-gce-startup.sh) | **GCE startup script:** swap, Docker, clone/build image, `docker run` with **`STUDIO_CORS_ORIGINS`** and **`STUDIO_COMFY_URL`** from instance metadata. |
| [`studio-cors-origins.txt`](./studio-cors-origins.txt) | One comma-separated line for **`gcloud --metadata-from-file=STUDIO_CORS_ORIGINS=…`** (commas safe). |
| [`install-cloudflared-debian.sh`](./install-cloudflared-debian.sh) | Install **cloudflared** on Debian/Ubuntu. |
| [`cloudflared-service-install.sh`](./cloudflared-service-install.sh) | **`cloudflared service install <token>`** (run as root) for **remotely managed** tunnels. |
| [`cloudflared-config-gce-immersive-api.yml`](./cloudflared-config-gce-immersive-api.yml) | Example **locally managed** named tunnel: **`api-origin.…` → 8787**, **`comfy.…` → 8188**. Match routes in Zero Trust if you use dashboard config instead. |
| [`cloudflared-config.yml.example`](./cloudflared-config.yml.example) | Generic named-tunnel template. |
| [`add-swap-2g.sh`](./add-swap-2g.sh) | 2 GiB swap before heavy `docker build`. |
| [`setup-cloudflare-dns-for-studio.ps1`](./setup-cloudflare-dns-for-studio.ps1) | PowerShell: API DNS helpers (needs **`CLOUDFLARE_API_TOKEN`**). |
| [`setup-cloudflare-vercel-dns.ps1`](./setup-cloudflare-vercel-dns.ps1) | Apex/`www` targets when the zone is on Cloudflare. |
| [`import-zone-to-cloudflare.ps1`](./import-zone-to-cloudflare.ps1) | Onboard a zone to Cloudflare (then change nameservers at registrar). |
| [`verify-studio-public-health.sh`](./verify-studio-public-health.sh) | **Laptop / CI:** DNS + `curl` **`api-origin`** and **`api`** health (read-only). |
| [`vm-check-studio-stack.sh`](./vm-check-studio-stack.sh) | **GCE VM (SSH):** `cloudflared`, `docker`, `127.0.0.1:8787` health, **Blender** in `studio-worker` container. |
| [`cloudflared-connector-immersive-labs-studio-api.template.yml`](./cloudflared-connector-immersive-labs-studio-api.template.yml) | **Named tunnel ingress:** `api-origin` → `8787`, `comfy` → `8188`. Copy to the connector host; set `credentials-file` path; run `cloudflared tunnel run`. |
| [`gce-ssh-immersive-studio-worker.ps1`](./gce-ssh-immersive-studio-worker.ps1) | **Windows:** IAP SSH using **OpenSSH** instead of PuTTY (`CLOUDSDK_COMPUTE_SSH_WITH_NATIVE_OPENSSH=1`). |

**Tunnel had no connectors (HTTP 530):** start `cloudflared` on a host that can reach `127.0.0.1:8787` (VM with Docker, or your dev PC while testing). A working Windows example lives at `%USERPROFILE%\.cloudflared\immersive-labs-studio-api-connector.yml` after you copy the template and point `credentials-file` at your `52513248-….json`.

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
- **`STUDIO_COMFY_URL`** — Base URL for ComfyUI’s HTTP API **as seen from the worker process**.
  - **Worker in Docker, ComfyUI on the VM host:** use **`https://comfy.immersivelabs.space`** (tunnel to host `127.0.0.1:8188`), **not** `http://127.0.0.1:8188` (that targets the container loopback → connection refused). Alternative: `http://host.docker.internal:8188` with `docker run --add-host=host.docker.internal:host-gateway`.
  - **ComfyUI on another host:** set to that host’s HTTPS URL.
  - **Worker and ComfyUI on the same host without Docker:** `http://127.0.0.1:8188` is fine.
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
