# Deploy the studio worker on a free GCP VM (e2-micro)

This guide runs **`immersive-studio serve`** on a small **Google Cloud** virtual machine that stays within the [always-free Compute Engine allowance](https://cloud.google.com/free/docs/free-cloud-features) when you use a single **`e2-micro`** instance in an eligible US region, a modest boot disk, and light traffic.

**Why GCP here:** signup and quotas are usually straightforward, docs are stable, and **`e2-micro`** is a common choice for always-free hobby APIs.

**What you get:** a public HTTPS URL for the worker that pairs with the static site on Vercel (`VITE_STUDIO_API_URL` at build time). **You do not keep your laptop online.**

**Caveats:**

- You need a **billing account** on GCP; staying free depends on **staying inside** free-tier limits. Check **Billing → Reports** after setup.
- **`e2-micro` has 1 GiB RAM.** Full **Ollama / ComfyUI / Blender** on the same VM is usually unrealistic. Plan on **mock specs** and lightweight jobs first.
- The Vercel app is **HTTPS**; the worker must be **HTTPS** too (mixed content). Use **Cloudflare Tunnel** (below) or Caddy.

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
  -e STUDIO_CORS_ORIGINS='https://your-app.vercel.app,https://www.yourdomain.com,https://yourdomain.com' \
  -v studio-output:/repo/apps/studio-worker/output \
  immersive-studio-worker:local
```

9. On the VM, verify: **`curl -sS http://127.0.0.1:8787/api/studio/health`**

### Cloudflare Tunnel

10. In [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels** → **Create tunnel**.
11. Choose **Cloudflared** on **Debian** and copy the **`cloudflared service install`** **token** (JWT).
12. On the VM: **`bash scripts/studio-cloudflare-tunnel/install-cloudflared-debian.sh`**
13. On the VM: **`sudo bash scripts/studio-cloudflare-tunnel/cloudflared-service-install.sh 'PASTE_TOKEN'`**
14. In the tunnel → **Public hostname**: subdomain **`api`**, domain your zone, service **HTTP**, URL **`http://127.0.0.1:8787`** (must match the tunnel docs and your DNS name, e.g. **`https://api.yourdomain.com`**).

### DNS (domain on Vercel)

15. In **Vercel → Project → Domains → your domain → DNS**, add **CNAME**:  
    **Name:** `api` (or your subdomain) → **Value:** **`<TUNNEL_ID>.cfargotunnel.com`** (from Cloudflare tunnel details).  
    (If nameservers are **Cloudflare** instead, use automatic DNS in the tunnel UI and skip manual CNAME on Vercel.)
16. Wait for DNS to propagate; test: **`curl -sS https://api.yourdomain.com/api/studio/health`**

### Vercel (frontend)

17. Project → **Settings → Environment Variables**: **`VITE_STUDIO_API_URL`** = **`https://api.yourdomain.com`** (no trailing slash; use your real API host).
18. **Redeploy** the production deployment so the bundle includes that variable.
19. Confirm **`STUDIO_CORS_ORIGINS`** on the worker lists **both** **`https://your-app.vercel.app`** and **`https://www.yourdomain.com`** / **`https://yourdomain.com`** if you use those URLs in the browser (see below).
20. Open **`/studio`** on each live origin you use and confirm the health line shows the worker OK.

### `STUDIO_CORS_ORIGINS` (production pattern)

The browser sends an **`Origin`** header that must **exactly** match one allowed origin (scheme + host; no path). List **all** of these, comma-separated, if you use them:

| You open the site at | Include in `STUDIO_CORS_ORIGINS` |
|----------------------|----------------------------------|
| Default Vercel URL | `https://your-app.vercel.app` |
| `www` custom domain | `https://www.yourdomain.com` |
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

---

## 11. Full runbook (all commands in order)

Use this as a single path from “nothing on the VM” to “HTTPS worker + Vercel”. Replace placeholders before pasting.

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

## Related

- Worker HTTP API: [`apps/studio-worker/README.md`](../../apps/studio-worker/README.md)
- Frontend API base: [`apps/web/src/studioApiConfig.ts`](../../apps/web/src/studioApiConfig.ts)
