# Security and operations checklist (Studio API)

Use this when onboarding a new environment or reviewing production.

## API keys and tenants

- [ ] **`STUDIO_API_AUTH_REQUIRED=1`** in production; keys issued via **`immersive-studio tenants issue-key`** (or your operator runbook).
- [ ] Rotate keys after staff changes; revoke in **`tenants.sqlite`** / Postgres tenants table as needed.
- [ ] **`STUDIO_CORS_ORIGINS`** lists only real browser origins (marketing site, Vercel previews you trust). Avoid `*` with **`allow_credentials`**.

## Edge and tunnel

- [ ] **`ORIGIN_URL`** on the Cloudflare Worker points at **`api-origin…`** (tunnel), not **`api…`** (Worker loop).
- [ ] Tunnel hostname for origin is **DNS only (grey cloud)** if you bypass Cloudflare features on that record.
- [ ] Review Worker logs and **`studio.access`** lines (`request_id`, path, status, `elapsed_ms`) after incidents.

## Abuse and capacity

- [ ] **`STUDIO_RATE_LIMIT_ENQUEUE_PER_MINUTE`** (default **60** per key/IP bucket); set **`0`** only in isolated dev.
- [ ] **`STUDIO_OLLAMA_READ_TIMEOUT_S`** and **`STUDIO_OLLAMA_MODEL`** match VM capacity; use **`STUDIO_OLLAMA_STREAM=1`** only after validating Ollama supports streaming for your model.
- [ ] Alerts on **`/api/studio/metrics`**: high **`slo.pending_oldest_age_seconds`**, **`slo.running_oldest_age_seconds`**, or queue **`dead`** counts.

## Billing

- [ ] Stripe webhook secret and price envs set; test mode vs live mode consistent across Dashboard and Worker.
