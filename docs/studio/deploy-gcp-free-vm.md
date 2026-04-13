# Deploy the studio worker on a free GCP VM (e2-micro)

This guide runs **`immersive-studio serve`** on a small **Google Cloud** virtual machine that stays within the [always-free Compute Engine allowance](https://cloud.google.com/free/docs/free-cloud-features) when you use a single **`e2-micro`** instance in an eligible US region, a modest boot disk, and light traffic.

**Why GCP here:** signup and quotas are usually straightforward, docs are stable, and **`e2-micro`** is a common choice for always-free hobby APIs.

**What you get:** a public HTTPS URL for the worker that pairs with your static frontend (e.g. **Cloudflare Pages**), with **`VITE_STUDIO_API_URL` set at Vite build time**. **You do not keep your laptop online.**

**Caveats:**

- You need a **billing account** on GCP; staying free depends on **staying inside** free-tier limits. Check **Billing → Reports** after setup.
- **`e2-micro` has 1 GiB RAM.** Full **Ollama / ComfyUI / Blender** on the same VM is usually unrealistic. Plan on **mock specs** and lightweight jobs first.
- The marketing site is served over **HTTPS**; the worker must be **HTTPS** too (mixed content). Use **Cloudflare Tunnel** (below) or Caddy.

**Automation:** [`scripts/studio-cloudflare-tunnel/`](../../scripts/studio-cloudflare-tunnel/) — see [§10](#10-terminal-scripts-this-repo).

---

## Complete setup checklist (GCP + Cloudflare Tunnel)

Do these in order. Replace placeholders (`YOUR_PROJECT_ID`, `your-app`, `yourdomain.com`, etc.) with your values.

### Google Cloud

1. Install [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) on your laptop.
2. Run **`gcloud auth login`** and **`gcloud config set project YOUR_PROJECT_ID`**.
3. **Create the VM** (console or script):
   - From the monorepo: **`bash scripts/studio-cloudflare-tunnel/gcp-create-e2-vm.sh`**  
     Optional: **`ZONE=us-central1-a VM_NAME=immersive-studio-worker`** before the command.
   - Or manually: Compute Engine → **e2-micro**, Ubuntu **22.04 LTS**, disk **≤30 GiB**, tag **`immersive-studio-ssh`**, firewall allowing **TCP 22** only (tunnel needs no public 443/8787 on GCP).
4. **SSH into the VM:**  
   **`gcloud compute ssh immersive-studio-worker --zone=YOUR_ZONE`**

### On the VM — Docker and worker

5. **Add swap** (avoids OOM during `docker build`). Either clone the repo and run **`bash scripts/studio-cloudflare-tunnel/add-swap-2g.sh`**, or paste the **inline commands** in [§2](#2-add-swap-recommended-before-docker-build) (no clone required).
6. **Install Docker** ([Ubuntu guide](https://docs.docker.com/engine/install/ubuntu/)), then **`sudo usermod -aG docker "$USER"`** and log out/in.
7. **Clone the monorepo** and build:  
   **`git clone …`** → **`cd immersive.labs`** →  
   **`docker build -f apps/studio-worker/Dockerfile -t immersive-studio-worker:local .`**
8. **Run the container** bound to **localhost** (tunnel will reach it). Set **`STUDIO_CORS_ORIGINS`** to **every origin** visitors use for your site (comma-separated, no paths — see [CORS](#studio_cors_origins-production-pattern)):

```bash
docker run -d --name studio-worker --restart unless-stopped \
  -p 127.0.0.1:8787:8787 \
  -e STUDIO_CORS_ORIGINS='https://your-project.pages.dev,https://www.yourdomain.com,https://yourdomain.com' \
  -v studio-output:/repo/apps/studio-worker/output \
  immersive-studio-worker:local
```

9. On the VM, verify: **`curl -sS http://127.0.0.1:8787/api/studio/health`**

### ComfyUI and `STUDIO_COMFY_URL` (textures)

The worker calls ComfyUI’s HTTP API at **`STUDIO_COMFY_URL`** (no trailing slash). **Important for same-VM setups:**

- If the worker runs **inside Docker** and ComfyUI runs on the **VM host** (typical), **do not** set `STUDIO_COMFY_URL=http://127.0.0.1:8188` — that is the container’s own loopback and will get **connection refused**. Use **`https://comfy.immersivelabs.space`** (tunnel to host `127.0.0.1:8188`) or **`http://host.docker.internal:8188`** with `docker run --add-host=host.docker.internal:host-gateway`. The GCE startup script now defaults to the **HTTPS** public URL.
- Add a **second tunnel public hostname** (e.g. **`comfy.yourdomain.com`**) → **`http://127.0.0.1:8188`** only if you need **external** HTTPS access to ComfyUI; that is separate from the worker’s loopback URL.
- The GCE startup script [`vm-bootstrap-gce-startup.sh`](../../scripts/studio-cloudflare-tunnel/vm-bootstrap-gce-startup.sh) reads **`STUDIO_COMFY_URL`** from instance metadata (default **`http://127.0.0.1:8188`** when unset). Set metadata or recreate the container after changes.
- Script index and tunnel notes: [`scripts/studio-cloudflare-tunnel/README.md`](../../scripts/studio-cloudflare-tunnel/README.md).

**User-facing summary:** the deployed site includes **`/docs`** (`apps/web`) describing this split (loopback vs public hostname).

### Ollama and `STUDIO_OLLAMA_URL` / `STUDIO_OLLAMA_MODEL` (LLM spec generation)

The worker calls Ollama’s HTTP API at **`STUDIO_OLLAMA_URL`** (default in code `http://127.0.0.1:11434`). **Inside Docker**, that URL is the **container** loopback — you will get **connection refused** unless Ollama runs in the same container (it does not in our image).

**Fix (same pattern as Comfy):**

1. Install Ollama on the **VM host** (not only in Docker): from the repo on the VM, **`sudo bash scripts/studio-cloudflare-tunnel/install-ollama-debian-vm.sh`** (sets `OLLAMA_HOST=0.0.0.0:11434` so Docker can reach it). On **e2-micro** / small disks, the script defaults to **`tinyllama`** (~637 MB); use **`OLLAMA_FIRST_PULL=llama3.2`** only if you have free space ( **`llama3.2`** is ~2 GB ).
2. Recreate **`studio-worker`** via **`vm-rebuild-studio-worker.sh`** / bootstrap: **default is Docker `--network host`**, **`STUDIO_OLLAMA_URL=http://127.0.0.1:11434`**, and **`immersive-studio serve --host 127.0.0.1 --port 8787`** so the API stays on loopback (tunnel unchanged) and Ollama is reached without bridge/UFW hairpin. Set instance metadata **`STUDIO_DOCKER_NETWORK=bridge`** to restore **`-p 127.0.0.1:8787:8787`** + bridge **`STUDIO_OLLAMA_URL`** (dynamic gateway, default **`172.17.0.1`**). Override **`STUDIO_OLLAMA_URL`** / **`STUDIO_OLLAMA_MODEL`** via metadata anytime.
3. **`install-ollama-debian-vm.sh`** may add **`ufw`** allow rules for **`172.17/16`** and **`172.18/16` → 11434** when UFW is active (helps **bridge** mode). With **host** networking, Ollama on **`127.0.0.1:11434`** does not cross the bridge.
4. **Mock mode** in `/studio` skips Ollama entirely if you only need wiring tests.

### Cloudflare Tunnel

10. In [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels** → **Create tunnel**.
11. Choose **Cloudflared** on **Debian** and copy the **`cloudflared service install`** **token** (JWT).
12. On the VM: **`bash scripts/studio-cloudflare-tunnel/install-cloudflared-debian.sh`**
13. On the VM: **`sudo bash scripts/studio-cloudflare-tunnel/cloudflared-service-install.sh 'PASTE_TOKEN'`**
14. In the tunnel → **Public hostname**: subdomain **`api`**, domain your zone, service **HTTP**, URL **`http://127.0.0.1:8787`** (must match the tunnel docs and your DNS name, e.g. **`https://api.yourdomain.com`**).

### DNS (API hostname)

15. Where your **apex / `www`** DNS lives (registrar, **Cloudflare DNS**, or a former static host): add a **CNAME** for the API subdomain:  
    **Name:** `api` (or your subdomain) → **Value:** **`<TUNNEL_ID>.cfargotunnel.com`** (from Cloudflare tunnel details).  
    If the zone is already on **Cloudflare**, you can use automatic DNS from the tunnel UI instead of a manual CNAME.
16. Wait for DNS to propagate; test: **`curl -sS https://api.yourdomain.com/api/studio/health`**

### Cloudflare Pages (frontend)

17. **Cloudflare Dashboard** → **Workers & Pages** → your **Pages** project → **Settings** → **Environment variables**: set **`VITE_STUDIO_API_URL`** = **`https://api.yourdomain.com`** (no trailing slash; use your real API host).
18. **Trigger a new production deployment** so the bundle includes that variable (Vite inlines `VITE_*` at build time).
19. Confirm **`STUDIO_CORS_ORIGINS`** on the worker lists **every origin** visitors use — e.g. **`https://www.yourdomain.com`**, **`https://yourdomain.com`**, and any **`*.pages.dev`** preview URL if you test against production APIs from preview deploys (see below).
20. Open **`/studio`** on each live origin you use and confirm the health line shows the worker OK.

### After changing `apps/studio-worker` (Python fixes)

The **Pages/CI build** only ships the **React** app. Any change under **`apps/studio-worker`** (validation, queue, billing, Comfy integration) requires updating the **machine that runs `immersive-studio serve`** (your VM/container), not Cloudflare Pages alone.

1. **On the worker host:** `git pull` (or copy the new tree), then rebuild and recreate the container from the monorepo root, for example:  
   `docker build -f apps/studio-worker/Dockerfile -t immersive-studio-worker:local .`  
   then `docker stop` / `docker rm` the old container and `docker run …` again with the same **`-e`** flags (`STUDIO_CORS_ORIGINS`, `STUDIO_COMFY_URL`, secrets, etc.).  
   **From your laptop** (with `gcloud` and SSH to the VM): run **`bash scripts/studio-cloudflare-tunnel/vm-remote-rebuild-studio-worker.sh`** — it resets **`/opt/immersive.labs`** to **`origin/main`** and runs **[`vm-rebuild-studio-worker.sh`](../../scripts/studio-cloudflare-tunnel/vm-rebuild-studio-worker.sh)** (metadata-driven **`docker run`**). Use **`IAP=1`** if you reach the VM only via IAP.
2. **Smoke test:** `curl -sS https://api.yourdomain.com/api/studio/health` — the JSON should include **`worker_version`** (bumped in `apps/studio-worker` when you ship server-side fixes). The **`/studio`** page shows **Worker v…** when that field is present so you can confirm the browser is talking to the redeployed API.
3. **Frontend:** Redeploy **Cloudflare Pages** only when **`apps/web`** or env vars such as **`VITE_STUDIO_API_URL`** change.

### `STUDIO_CORS_ORIGINS` (production pattern)

The browser sends an **`Origin`** header that must **exactly** match one allowed origin (scheme + host; no path). List **all** of these, comma-separated, if you use them:

| You open the site at | Include in `STUDIO_CORS_ORIGINS` |
|----------------------|----------------------------------|
| Cloudflare Pages preview | `https://your-branch.your-project.pages.dev` (only if you hit the API from previews) |
| Custom domain (`www`) | `https://www.yourdomain.com` |
| Apex custom domain | `https://yourdomain.com` |

Optional local dev: append **`http://127.0.0.1:5173,http://localhost:5173`**. Trailing slashes in the env var are stripped by the worker.

**After changing CORS:** recreate the container with the new **`-e STUDIO_CORS_ORIGINS=...`** (or `docker stop` / `rm` / `run` again).

---

## 1. Create the VM

**Option A — Console:** [Google Cloud Console](https://console.cloud.google.com/) → Compute Engine → VM instances → Create.

**Option B — Terminal (laptop):**

```bash
bash scripts/studio-cloudflare-tunnel/gcp-create-e2-vm.sh
```

Optional: `ZONE=us-east1-b VM_NAME=my-worker bash scripts/studio-cloudflare-tunnel/gcp-create-e2-vm.sh`

**Instance settings:** **`e2-micro`**, Ubuntu **22.04 LTS**, disk **≤30 GiB**, tag **`immersive-studio-ssh`**, SSH-only firewall when using a tunnel.

**SSH:** `gcloud compute ssh VM_NAME --zone=ZONE`

---

## 2. Add swap (recommended before `docker build`)

**On the VM** — use **either** the script (only after you’ve cloned the repo) **or** these commands (works on a fresh VM with no repo):

```bash
if [[ -f /swapfile ]]; then
  echo "/swapfile already exists — nothing to do."
else
  sudo fallocate -l 2G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  echo "2G swap enabled."
fi
```

**Or**, from a cloned monorepo root: **`bash scripts/studio-cloudflare-tunnel/add-swap-2g.sh`**

---

## 3. Install Docker Engine

Follow [Docker’s Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/). Then:

```bash
sudo usermod -aG docker "$USER"
```

Log out and back in.

---

## 4. Build and run the worker image

**On the VM**, from the **repository root**:

```bash
git clone https://github.com/<your-org>/immersive.labs.git
cd immersive.labs
docker build -f apps/studio-worker/Dockerfile -t immersive-studio-worker:local .
```

```bash
docker run -d --name studio-worker --restart unless-stopped \
  -p 127.0.0.1:8787:8787 \
  -e STUDIO_CORS_ORIGINS='https://YOUR-APP.vercel.app,https://www.yourdomain.com,https://yourdomain.com' \
  -v studio-output:/repo/apps/studio-worker/output \
  immersive-studio-worker:local
```

**Compose:** the checked-in file binds **8787** on all interfaces for local dev; on GCP + tunnel prefer **`127.0.0.1:8787:8787`** as above.

---

## 5. HTTPS — Cloudflare Tunnel

### 5a. Create the tunnel (Cloudflare dashboard)

1. **Zero Trust** → **Networks** → **Tunnels** → **Create tunnel**.
2. Copy the **`sudo cloudflared service install …`** token.

### 5b–5c. On the VM

```bash
bash scripts/studio-cloudflare-tunnel/install-cloudflared-debian.sh
sudo bash scripts/studio-cloudflare-tunnel/cloudflared-service-install.sh 'PASTE_TOKEN_HERE'
```

### 5d. Public hostname

**Subdomain** `api`, **HTTP** → **`http://127.0.0.1:8787`**.

### 5e. Vercel-purchased domain DNS

**CNAME** `api` → **`<TUNNEL_ID>.cfargotunnel.com`** in Vercel DNS, or move DNS to Cloudflare and use tunnel auto-DNS.

---

## 6. HTTPS — Caddy (alternative)

Point **`studio-api.yourdomain.com`** A record at the VM; install **Caddy** → **`127.0.0.1:8787`**; open **443/80** on GCP firewall.

---

## 7. Wire up Vercel (frontend)

1. **`VITE_STUDIO_API_URL`** = **`https://api.yourdomain.com`** (no trailing slash).
2. **Redeploy.**
3. **`STUDIO_CORS_ORIGINS`** includes every browser origin you use (see [checklist](#studio_cors_origins-production-pattern)).

---

## 8. Smoke checks

```bash
curl -sS "https://YOUR-WORKER-ORIGIN/api/studio/health"
```

Open **`/studio`** on Vercel; health should show the worker reachable.

---

## 9. Operations notes

- **Persistence:** volume **`studio-output`** → **`/repo/apps/studio-worker/output`**
- **Upgrades:** `git pull`, rebuild image, recreate container
- **Auth / billing:** [`apps/studio-worker/README.md`](../../apps/studio-worker/README.md)

---

## 10. Terminal scripts (this repo)

| Script | Where to run | Purpose |
|--------|----------------|--------|
| [`gcp-create-e2-vm.sh`](../../scripts/studio-cloudflare-tunnel/gcp-create-e2-vm.sh) | Laptop (`gcloud` logged in) | **`e2-micro`** + SSH firewall rule |
| [`add-swap-2g.sh`](../../scripts/studio-cloudflare-tunnel/add-swap-2g.sh) | VM | 2 GiB swap |
| [`install-cloudflared-debian.sh`](../../scripts/studio-cloudflare-tunnel/install-cloudflared-debian.sh) | VM | Install **cloudflared** |
| [`cloudflared-service-install.sh`](../../scripts/studio-cloudflare-tunnel/cloudflared-service-install.sh) | VM as **root** | `cloudflared service install <token>` |
| [`cloudflared-config.yml.example`](../../scripts/studio-cloudflare-tunnel/cloudflared-config.yml.example) | Reference | Optional locally managed tunnel |
| [`studio-cors-origins.txt`](../../scripts/studio-cloudflare-tunnel/studio-cors-origins.txt) | Laptop | **Production** CORS list for `gcloud --metadata-from-file=STUDIO_CORS_ORIGINS=…` |
| [`setup-cloudflare-dns-for-studio.ps1`](../../scripts/studio-cloudflare-tunnel/setup-cloudflare-dns-for-studio.ps1) | Laptop (PowerShell) | **API:** create `api` → `<tunnel-id>.cfargotunnel.com` in the correct Cloudflare zone. Defaults to **proxied (orange cloud)** so IPv4 clients get Cloudflare anycast; grey-cloud-only chains often break **Windows / IPv4-only** resolution. Needs **`CLOUDFLARE_API_TOKEN`** (**Zone → DNS → Edit**). |
| [`import-zone-to-cloudflare.ps1`](../../scripts/studio-cloudflare-tunnel/import-zone-to-cloudflare.ps1) | Laptop (PowerShell) | **API:** add **`immersivelabs.space`** to your Cloudflare account (`POST /zones`, `jump_start`). Needs token with **Zone → Zone → Create** + **Account → Account Settings → Read** (or set **`CLOUDFLARE_ACCOUNT_ID`**). You must still **change nameservers at the registrar** (e.g. Vercel) to the printed `*.ns.cloudflare.com` pair. |
| [`setup-cloudflare-vercel-dns.ps1`](../../scripts/studio-cloudflare-tunnel/setup-cloudflare-vercel-dns.ps1) | Laptop (PowerShell) | After the zone is on Cloudflare: **apex `A` → Vercel** (`76.76.21.21`) + **`www` CNAME → `cname.vercel-dns.com`** (grey cloud). Without these, **`immersivelabs.space` / `www` do not resolve** (only `api` existed). Confirm values in **Vercel → Domains** if your project shows different targets. |

---

## 11. Full runbook (all commands in order)

Use this as a single path from “nothing on the VM” to “HTTPS worker + Vercel”. Replace placeholders before pasting.

<a id="gce-metadata-studio-cors-origins"></a>

### GCE metadata: `STUDIO_CORS_ORIGINS` (comma-safe)

`gcloud --metadata=...` treats **commas** as separators between keys, so use **`--metadata-from-file`** for multi-origin CORS.

This repo keeps the **production** Immersive Labs origins in one line (no placeholders):

**[`scripts/studio-cloudflare-tunnel/studio-cors-origins.txt`](../../scripts/studio-cloudflare-tunnel/studio-cors-origins.txt)**

From the **monorepo root** on your laptop:

```bash
gcloud compute instances add-metadata immersive-studio-worker \
  --zone=us-central1-a \
  --project=immersive-labs-studio \
  --metadata-from-file=STUDIO_CORS_ORIGINS=scripts/studio-cloudflare-tunnel/studio-cors-origins.txt
```

If you add or remove a public site URL, **edit that file** (one comma-separated line, no spaces unless inside a URL), commit, then re-run the command above and **reset** the VM (or recreate the container over SSH).

---

| Placeholder | Example |
|-------------|---------|
| `PROJECT` | `immersive-labs-studio` |
| `ZONE` | `us-central1-a` |
| `VM` | `immersive-studio-worker` |
| `REPO_URL` | `https://github.com/YOUR_ORG/immersive.labs.git` |
| `YOUR_VERCEL_APP` | `my-app` → origin `https://my-app.vercel.app` |
| `YOURDOMAIN` | Your apex domain (no `https://`) |
| `STUDIO_CORS` | Comma-separated origins, e.g. `https://YOUR_VERCEL_APP.vercel.app,https://www.example.com,https://example.com` |
| `API_SUBDOMAIN` | Usually `api` → public URL `https://api.example.com` |

### A. On your laptop (Git Bash or terminal with `gcloud`)

**1)** Log in and select project (once per machine):

```bash
gcloud auth login
gcloud config set project PROJECT
```

**2)** SSH into the VM (replace `PROJECT`, `ZONE`, `VM`):

```bash
gcloud compute ssh VM --zone=ZONE --project=PROJECT
```

If Windows prompts about SSH keys or PuTTY, use **Compute Engine → VM → SSH** in the browser instead; you get the same shell on the VM.

---

### B. On the GCP VM (paste in order)

**3)** Swap (safe to re-run; skips if `/swapfile` exists):

```bash
if [[ -f /swapfile ]]; then
  echo "/swapfile already exists — nothing to do."
else
  sudo fallocate -l 2G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  echo "2G swap enabled."
fi
free -h
```

**4)** Git and Docker:

```bash
sudo apt-get update
sudo apt-get install -y git ca-certificates curl
curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
sudo sh /tmp/get-docker.sh
sudo usermod -aG docker "$USER"
```

**5)** Apply the `docker` group **without logging out** (or exit SSH, SSH back in):

```bash
newgrp docker
```

**6)** Clone and build the worker image (monorepo **root** = build context):

```bash
cd ~
git clone REPO_URL immersive.labs
cd immersive.labs
docker build -f apps/studio-worker/Dockerfile -t immersive-studio-worker:local .
```

**7)** Run the worker (localhost only; **edit `STUDIO_CORS`** to match every URL you use in the browser):

```bash
docker run -d --name studio-worker --restart unless-stopped \
  -p 127.0.0.1:8787:8787 \
  -e STUDIO_CORS_ORIGINS='STUDIO_CORS' \
  -v studio-output:/repo/apps/studio-worker/output \
  immersive-studio-worker:local
```

**8)** Health check on the VM:

```bash
curl -sS http://127.0.0.1:8787/api/studio/health
```

You should see JSON with `"status":"ok"`.

---

### C. Cloudflare Tunnel (dashboard + VM)

**9)** In a browser: [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels** → **Create tunnel**.

**10)** Name the tunnel (e.g. `immersive-studio`), choose **Install connector** → **Debian** (or copy the **token** from the `cloudflared service install …` command). **Copy the JWT token** only (the long string in quotes).

**11)** Back on the **VM**, install `cloudflared`:

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
sudo apt-get update
sudo apt-get install -y cloudflared
```

**12)** Install and start the tunnel service (**paste your real token**):

```bash
sudo cloudflared service install 'PASTE_YOUR_TUNNEL_TOKEN_HERE'
sudo systemctl enable cloudflared
sudo systemctl restart cloudflared
sudo systemctl status cloudflared --no-pager
```

**13)** In Zero Trust → your tunnel → **Public Hostname** → **Add**:

- **Subdomain:** `API_SUBDOMAIN` (e.g. `api`)
- **Domain:** `YOURDOMAIN` (your zone in Cloudflare / DNS)
- **Service type:** HTTP
- **URL:** `http://127.0.0.1:8787`

Save.

**14)** DNS:

- If the domain uses **Vercel nameservers**: **Vercel → Domains → DNS** → **CNAME**: name **`api`** (or your subdomain), target **`<TUNNEL_ID>.cfargotunnel.com`** (tunnel UUID from Cloudflare tunnel page).
- If the domain is on **Cloudflare DNS**: use the tunnel UI **Configure DNS** / automatic route when offered.

**15)** From your laptop (after DNS propagates):

```bash
curl -sS "https://api.YOURDOMAIN/api/studio/health"
```

---

### D. Vercel (frontend)

**16)** Project → **Settings → Environment Variables** (Production):

- **`VITE_STUDIO_API_URL`** = `https://api.YOURDOMAIN` (no trailing slash)

**17)** **Redeploy** production (Deployments → … → Redeploy).

**18)** Open `https://YOUR_VERCEL_APP.vercel.app/studio` (and your custom domain if applicable). If the UI says the worker is unreachable, recheck **`STUDIO_CORS_ORIGINS`** matches **exactly** each origin you use, then recreate the container:

```bash
docker stop studio-worker && docker rm studio-worker
docker run -d --name studio-worker --restart unless-stopped \
  -p 127.0.0.1:8787:8787 \
  -e STUDIO_CORS_ORIGINS='STUDIO_CORS' \
  -v studio-output:/repo/apps/studio-worker/output \
  immersive-studio-worker:local
```

---

### E. Later: update worker code

```bash
cd ~/immersive.labs && git pull
docker build -f apps/studio-worker/Dockerfile -t immersive-studio-worker:local .
docker stop studio-worker && docker rm studio-worker
# re-run the same docker run ... as in step 7
```

---

## 12. Operator guide — what you do after a VM reset (elaborated)

Use this when the VM runs the [GCE startup script](../../scripts/studio-cloudflare-tunnel/vm-bootstrap-gce-startup.sh): install swap/Docker, clone/build once, then start **`studio-worker`** only if **`STUDIO_CORS_ORIGINS`** instance metadata is set.

**On your laptop you need:** [Google Cloud SDK](https://cloud.google.com/sdk/docs/install), this repo cloned, and a shell where **`gcloud auth login`** already succeeded for the right Google account.

**Names below** match the example in [§11](#gce-metadata-studio-cors-origins): VM **`immersive-studio-worker`**, zone **`us-central1-a`**, project **`immersive-labs-studio`**. Change them if yours differ.

<a id="op-12-cors-metadata"></a>

### 12.1 Set `STUDIO_CORS_ORIGINS` on the instance (laptop, before or between resets)

**Why:** The startup script reads **instance metadata** (not a file on the VM). Comma-separated origins break **`gcloud --metadata=KEY=val1,val2`** because commas separate keys — so use **`--metadata-from-file`**.

**What you do:**

1. Open a terminal on your **laptop**.
2. **`cd`** to the **monorepo root** (the folder that contains **`scripts/`** and **`apps/`**), e.g. `cd ~/Desktop/vibe-code/immersive.labs`.
3. Open [`studio-cors-origins.txt`](../../scripts/studio-cloudflare-tunnel/studio-cors-origins.txt) in an editor. Confirm the **single line** lists **every** browser origin you use (scheme + host, **no** path, **no** trailing slash). Production values are already there; edit only if you add/remove a public URL.
4. Run (paths are relative to monorepo root):

   ```bash
   gcloud compute instances add-metadata immersive-studio-worker \
     --zone=us-central1-a \
     --project=immersive-labs-studio \
     --metadata-from-file=STUDIO_CORS_ORIGINS=scripts/studio-cloudflare-tunnel/studio-cors-origins.txt
   ```

5. **Success:** `gcloud` prints **Updated** / **metadata** without errors. **Failure:** if you see **file not found**, you are not in the repo root or the path is wrong — fix **`cd`** or the path after **`=`**.

**Note:** **`add-metadata`** **merges** keys; it does not delete unrelated metadata. You can run it again after editing the text file.

<a id="op-12-reset-vm"></a>

### 12.2 Reset the VM (laptop)

**Why:** Startup metadata is read **at boot** (and the long bootstrap path runs on early boots). A **reset** is a clean way to re-run startup after you set CORS.

**What you do:**

1. [Google Cloud Console](https://console.cloud.google.com/) → **Compute Engine** → **VM instances** → your VM → **Reset** (confirm), **or** from the laptop:

   ```bash
   gcloud compute instances reset immersive-studio-worker \
     --zone=us-central1-a \
     --project=immersive-labs-studio
   ```

2. Expect the instance to go **off** briefly and come back **Running** within **1–2 minutes**.

---

### 12.3 Wait (laptop — patience)

**First-ever bootstrap** (no prior successful **`Bootstrap complete`** on this disk): the script may install packages, **clone**, and **`docker build`** — often **10–20+ minutes** on **`e2-micro`** (swap helps).

**Already bootstrapped** (file **`/var/lib/immersive-studio-bootstrapped`** exists on the VM): the script takes a **fast path** — start Docker and **`docker start studio-worker`** — usually **1–3 minutes** after SSH port responds.

**Rule of thumb:** after reset, wait **at least 3 minutes** before concluding failure; if you know a full build is running, wait **15–20 minutes**.

---

### 12.4 Read serial port output (laptop)

**Why:** Startup logs go to the serial console; you can see **build finished**, **CORS missing**, or **errors** without SSH.

**What you do:**

1. Stay on the laptop; monorepo root is optional for this command.

2. **Filter** (high signal):

   ```bash
   gcloud compute instances get-serial-port-output immersive-studio-worker \
     --zone=us-central1-a \
     --project=immersive-labs-studio \
     --port=1 | grep -iE "Docker image built|Bootstrap complete|STUDIO_CORS|startup-script|failed|ERROR"
   ```

3. **Interpret:**

   - **`Docker image built.`** — image build finished at least once.
   - **`Bootstrap complete; studio-worker running.`** — container should be up with CORS from metadata.
   - **`STUDIO_CORS_ORIGINS is not set in instance metadata.`** — metadata empty or wrong key; do [§12.1](#op-12-cors-metadata) again, then [§12.2](#op-12-reset-vm).
   - **`startup-script`**, **`failed`**, **`ERROR`** — get **more context**:

     ```bash
     gcloud compute instances get-serial-port-output immersive-studio-worker \
       --zone=us-central1-a \
       --project=immersive-labs-studio \
       --port=1 | tail -n 200
     ```

4. Optional: on the VM, **`sudo tail -f /var/log/immersive-studio-bootstrap.log`** repeats the same bootstrap log to a file.

---

### 12.5 SSH into the VM and verify the worker locally (VM console)

**Why:** Confirm Docker and **`127.0.0.1:8787`** before Cloudflare or Vercel.

**What you do:**

1. **SSH — pick one:**
   - **Browser (good on Windows):** Console → **Compute Engine** → **VM instances** → **SSH** next to the instance.
   - **Laptop terminal:** `gcloud compute ssh immersive-studio-worker --zone=us-central1-a --project=immersive-labs-studio`

2. **Docker running and container present:**

   ```bash
   sudo docker ps -a --filter name=studio-worker
   ```

   - **Running:** **STATUS** shows **Up** (often with a health or uptime). **Exited** means the container crashed — check **`sudo docker logs studio-worker`**.
   - If **no container** and serial said CORS was missing, fix metadata and reset again.

3. **Health on loopback** (tunnel and firewall are irrelevant here):

   ```bash
   curl -sS http://127.0.0.1:8787/api/studio/health
   ```

   **Success:** JSON including something like **`"status":"ok"`** (exact shape may vary by worker version). **Connection refused:** nothing listening — container not running or wrong port. **Timeout:** unusual on localhost; recheck **`docker ps`**.

---

### 12.6 Cloudflare Tunnel (if you have not finished it yet)

**Why:** Browsers need **HTTPS** to call your API from Vercel; the worker listens on **HTTP** on **localhost** only. **Cloudflare Tunnel** exposes **`https://api.yourdomain/...`** and forwards to **`http://127.0.0.1:8787`**.

**What you do (summary — full commands in [§11.C](#c-cloudflare-tunnel-dashboard--vm)):**

1. In a browser: [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels** → **Create tunnel** → get a **connector install** token (**Debian**).
2. On the **VM** (SSH): install **`cloudflared`**, then **`sudo cloudflared service install 'YOUR_TOKEN'`**, **`sudo systemctl enable --now cloudflared`**, **`sudo systemctl status cloudflared`** — **active (running)**.
3. In the tunnel UI → **Public hostname**: subdomain **`api`** (or yours), **HTTP** → **`http://127.0.0.1:8787`**.

Do **not** open GCP firewall **8787** to the world; the tunnel reaches localhost from inside the VM.

---

### 12.7 DNS for `api` (your domain / Vercel)

**What you do:**

1. In Cloudflare tunnel details, find the **CNAME target** (often **`<TUNNEL_ID>.cfargotunnel.com`**).
2. **If the domain’s DNS is on Vercel:** Vercel → **Project** (or Domains) → **Domains** → your domain → **DNS** → add **CNAME**: **name** `api` (or your API subdomain), **value** the tunnel hostname.
3. **If DNS is on Cloudflare:** use the tunnel UI **Configure DNS** when offered, or create the same CNAME there.
4. **Propagation:** can be **minutes to hours**. Check with **`nslookup api.yourdomain.com`** or an online DNS checker until it resolves to Cloudflare/tunnel-related targets.

---

### 12.8 Verify HTTPS from your laptop

**What you do:**

```bash
curl -sS "https://api.YOURDOMAIN/api/studio/health"
```

Use your real API host (e.g. **`api.immersivelabs.space`**). **Success:** same JSON as localhost health. **SSL or DNS errors:** fix tunnel + DNS first. **404 from Cloudflare:** wrong **Public hostname** path or tunnel route.

---

### 12.9 Vercel — point the frontend at the worker

**What you do:**

1. [Vercel Dashboard](https://vercel.com/dashboard) → your **web** project → **Settings** → **Environment Variables**.
2. **Production:** add or edit **`VITE_STUDIO_API_URL`** = **`https://api.YOURDOMAIN`** (**no** trailing slash). Save.
3. **Deployments** → latest **Production** deployment → **⋯** → **Redeploy** (or push a commit). **Why:** Vite bakes this value in at **build** time; changing the variable alone does not change an old deployment.

---

### 12.10 Browser check (each real origin)

**What you do:**

1. Open **`https://immersivelabs.vercel.app/studio`** (and each custom domain you use), matching [studio-cors-origins.txt](../../scripts/studio-cloudflare-tunnel/studio-cors-origins.txt).
2. Confirm the Studio UI loads and any **worker health** / connection indicator matches **OK**.
3. If the browser shows **CORS** errors in **DevTools → Network / Console**, the **`Origin`** of the page must **exactly** match one entry in **`STUDIO_CORS_ORIGINS`** on the running container (scheme + host; **`www`** vs apex are different origins).

---

### 12.11 Changing CORS **after** the VM has already reached “Bootstrap complete”

The startup script’s **fast path** (after **`/var/lib/immersive-studio-bootstrapped`** exists) only runs **`docker start studio-worker`** on boot — it does **not** re-read **`STUDIO_CORS_ORIGINS`** from metadata. So **editing metadata + reset** alone **does not** update an already-created container’s environment.

**What you do:** SSH to the VM, then **recreate** the container with the new **`STUDIO_CORS_ORIGINS`** (same pattern as [§11](#11-full-runbook-all-commands-in-order) step **7** / [checklist](#complete-setup-checklist-gcp--cloudflare-tunnel) step **8**), or temporarily use the **`docker run`** line from the runbook with your updated comma-separated origins.

---

## Related

- Worker HTTP API: [`apps/studio-worker/README.md`](../../apps/studio-worker/README.md)
- Frontend API base: [`apps/web/src/studioApiConfig.ts`](../../apps/web/src/studioApiConfig.ts)
