import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EngravedBackdrop } from "../components/EngravedBackdrop";
import { STUDIO_API_BASE, STUDIO_API_READY, studioWorkerDisplayOrigin } from "../studioApiConfig";
import "../App.css";
import "./StudioPage.css";

const API_KEY_STORAGE = "immersive_studio_api_key";

type StudioCategory = "prop" | "environment_piece" | "character_base" | "material_library";
type StudioStyle = "realistic_hd_pbr" | "anime_stylized" | "toon_bold";

type JobSummary = {
  job_id: string;
  folder: string;
  created_at: string;
  status: string;
  summary: string;
  has_textures: boolean;
  error: string | null;
};

type UsageInfo = {
  limits_enforced: boolean;
  tier_id: string;
  tier_name: string;
  period: string | null;
  credits_used: number;
  credits_cap: number | null;
  textures_allowed: boolean;
  max_concurrent_jobs: number | null;
};

type BillingStatus = {
  stripe_checkout_available: boolean;
  checkout_tiers: string[];
  portal_needs_customer?: boolean;
  stripe_customer_linked: boolean;
  stripe_subscription_id: string | null;
  tier_id: string;
};

/** True when the worker probed local Comfy but nothing accepted the TCP connection (Comfy not started). */
function comfyLocalhostRefused(detail: string | null | undefined, url: string): boolean {
  const u = (url ?? "").toLowerCase();
  const d = (detail ?? "").toLowerCase();
  const local = u.includes("127.0.0.1") || u.includes("localhost");
  const p8188 = u.includes(":8188") || u.includes("8188");
  if (!local || !p8188) {
    return false;
  }
  return (
    d.includes("refused") ||
    d.includes("10061") ||
    d.includes("econnrefused") ||
    d.includes("could not be made") ||
    d.includes("failed to establish")
  );
}

function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((d) => JSON.stringify(d)).join("; ");
  }
  if (detail && typeof detail === "object") {
    return JSON.stringify(detail);
  }
  return "Request failed";
}

/** Parse JSON bodies; proxies often return HTML 502 pages which break `response.json()`. */
async function readApiJson<T>(r: Response): Promise<T> {
  const text = await r.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    const t = text.trim();
    const snippet = t.slice(0, 220).replace(/\s+/g, " ");
    const html =
      t.startsWith("<!") || t.toLowerCase().startsWith("<html")
        ? " The response was HTML (typical of a gateway 502/504 or CDN timeout), not JSON."
        : "";
    throw new Error(`HTTP ${r.status}: invalid JSON.${html}${snippet ? ` Body: ${snippet}` : ""}`);
  }
}

const STUDIO_QUEUE_POLL_MS = 2000;
const STUDIO_QUEUE_MAX_WAIT_MS = 45 * 60 * 1000;

type QueueJobRow = {
  status: string;
  last_error?: string | null;
  result?: {
    job_id?: string;
    folder?: string;
    manifest?: Record<string, unknown>;
    spec?: Record<string, unknown>;
    output_dir?: string;
    zip_path?: string;
    texture_logs?: string[];
    mesh_logs?: string[];
    errors?: string[];
  } | null;
};

export function StudioPage() {
  const [prompt, setPrompt] = useState("");
  const [category, setCategory] = useState<StudioCategory>("prop");
  const [stylePreset, setStylePreset] = useState<StudioStyle>("toon_bold");
  const [mock, setMock] = useState(false);
  const [generateTextures, setGenerateTextures] = useState(false);
  const [exportMesh, setExportMesh] = useState(false);
  const [loading, setLoading] = useState(false);
  const [packLoading, setPackLoading] = useState(false);
  const [jobLoading, setJobLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [spec, setSpec] = useState<Record<string, unknown> | null>(null);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [packResult, setPackResult] = useState<{ output_dir: string; job_id: string } | null>(null);
  const [jobResult, setJobResult] = useState<{
    job_id: string;
    zip_path: string;
    errors: string[];
    texture_logs: string[];
    mesh_logs: string[];
  } | null>(null);
  const [health, setHealth] = useState<"checking" | "ok" | "error">("checking");
  /** Extra context when health check fails (e.g. Cloudflare 530 tunnel). */
  const [healthErrorHint, setHealthErrorHint] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [comfy, setComfy] = useState<{ reachable: boolean; url: string; detail: string | null } | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [jobsRoot, setJobsRoot] = useState<string | null>(null);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(API_KEY_STORAGE);
      if (stored) {
        setApiKey(stored);
      }
    } catch {
      /* private mode */
    }
  }, []);

  const authHeaders = useCallback((): Record<string, string> => {
    const h: Record<string, string> = {};
    const k = apiKey.trim();
    if (k) {
      h.Authorization = `Bearer ${k}`;
    }
    return h;
  }, [apiKey]);

  const persistApiKey = useCallback(() => {
    try {
      window.localStorage.setItem(API_KEY_STORAGE, apiKey.trim());
    } catch {
      /* ignore */
    }
  }, [apiKey]);

  const checkHealth = useCallback(() => {
    if (!STUDIO_API_READY) {
      setHealth("error");
      setHealthErrorHint(null);
      return;
    }
    setHealth("checking");
    setHealthErrorHint(null);
    fetch(`${STUDIO_API_BASE}/api/studio/health`)
      .then(async (r) => {
        if (!r.ok) {
          setHealth("error");
          if (r.status === 530) {
            setHealthErrorHint(
              "Cloudflare returned HTTP 530 (tunnel / origin unreachable). On the host behind your public API, start cloudflared and confirm the tunnel routes to immersive-studio on the expected port; see scripts/studio-cloudflare-tunnel/README.md.",
            );
          } else if (r.status >= 500) {
            setHealthErrorHint(`Gateway or server error (HTTP ${r.status}). Check the Worker / reverse proxy and the Python worker logs.`);
          } else {
            setHealthErrorHint(`Unexpected HTTP ${r.status} from ${STUDIO_API_BASE}/api/studio/health.`);
          }
          return;
        }
        try {
          const j = await readApiJson<{ auth_required?: boolean }>(r);
          setHealth("ok");
          setHealthErrorHint(null);
          setAuthRequired(Boolean(j?.auth_required));
        } catch {
          setHealth("error");
          setHealthErrorHint(
            "The URL responded, but the body was not JSON (often an error page in front of the API). Fix DNS / tunnel / Worker upstream so /api/studio/health returns the worker JSON.",
          );
        }
      })
      .catch(() => {
        setHealth("error");
        setHealthErrorHint("Network error — the browser could not complete a request to the Studio API (offline, CORS, or blocked).");
      });
  }, []);

  const refreshUsage = useCallback(() => {
    if (!STUDIO_API_READY) {
      return;
    }
    fetch(`${STUDIO_API_BASE}/api/studio/usage`, { headers: authHeaders() })
      .then(async (r) => {
        if (!r.ok) {
          return null;
        }
        try {
          return await readApiJson<UsageInfo>(r);
        } catch {
          return null;
        }
      })
      .then((u) => setUsage(u))
      .catch(() => setUsage(null));
  }, [authHeaders]);

  const refreshBilling = useCallback(() => {
    if (!STUDIO_API_READY) {
      return;
    }
    fetch(`${STUDIO_API_BASE}/api/studio/billing/status`, { headers: authHeaders() })
      .then(async (r) => {
        if (!r.ok) {
          return null;
        }
        try {
          return await readApiJson<BillingStatus>(r);
        } catch {
          return null;
        }
      })
      .then((b) => setBilling(b))
      .catch(() => setBilling(null));
  }, [authHeaders]);

  const refreshComfy = useCallback(() => {
    if (!STUDIO_API_READY) {
      setComfy(null);
      return;
    }
    fetch(`${STUDIO_API_BASE}/api/studio/comfy-status`)
      .then(async (r) => {
        try {
          return await readApiJson<{ reachable: boolean; url: string; detail: string | null }>(r);
        } catch {
          return { reachable: false, url: "", detail: "request failed" };
        }
      })
      .then(setComfy)
      .catch(() => setComfy({ reachable: false, url: "", detail: "request failed" }));
  }, []);

  const refreshJobs = useCallback(() => {
    if (!STUDIO_API_READY) {
      setJobs([]);
      return;
    }
    fetch(`${STUDIO_API_BASE}/api/studio/jobs`, { headers: authHeaders() })
      .then(async (r) => {
        try {
          return await readApiJson<{ jobs: JobSummary[]; jobs_root?: string }>(r);
        } catch {
          return { jobs: [] as JobSummary[] };
        }
      })
      .then((data) => {
        setJobs(data.jobs ?? []);
        if (data.jobs_root) {
          setJobsRoot(data.jobs_root);
        }
      })
      .catch(() => setJobs([]));
  }, [authHeaders]);

  useEffect(() => {
    if (!STUDIO_API_READY) {
      setHealth("error");
      return;
    }
    checkHealth();
    refreshComfy();
  }, [checkHealth, refreshComfy]);

  useEffect(() => {
    if (!STUDIO_API_READY) {
      return;
    }
    refreshJobs();
    refreshUsage();
    refreshBilling();
    // Full jobs (textures + mesh) saturate a small VM; fewer concurrent polls reduces pressure on tunnel/origin.
    const pollMs = jobLoading ? 30_000 : 5000;
    const t = window.setInterval(() => {
      refreshJobs();
      refreshUsage();
      refreshBilling();
    }, pollMs);
    return () => window.clearInterval(t);
  }, [refreshBilling, refreshJobs, refreshUsage, jobLoading]);

  async function onGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!STUDIO_API_READY) {
      setError("Worker URL is not configured. Set VITE_STUDIO_API_URL and rebuild, or run the dev server locally.");
      return;
    }
    setLoading(true);
    setError(null);
    setPackResult(null);
    setJobResult(null);
    try {
      const r = await fetch(`${STUDIO_API_BASE}/api/studio/generate-spec`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          prompt,
          category,
          style_preset: stylePreset,
          mock,
        }),
      });
      const data = await readApiJson<{
        detail?: unknown;
        spec?: Record<string, unknown>;
        meta?: Record<string, unknown>;
      }>(r);
      if (!r.ok) {
        throw new Error(formatApiDetail(data.detail));
      }
      if (!data.spec) {
        throw new Error("Response missing spec");
      }
      setSpec(data.spec);
      setMeta(data.meta ?? null);
    } catch (err) {
      setSpec(null);
      setMeta(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function onWritePack() {
    if (!spec || !STUDIO_API_READY) {
      return;
    }
    setPackLoading(true);
    setError(null);
    setPackResult(null);
    setJobResult(null);
    try {
      const outputName = `WebPack_${Date.now()}`;
      const r = await fetch(`${STUDIO_API_BASE}/api/studio/pack`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ spec, output_name: outputName }),
      });
      const data = await readApiJson<{
        detail?: unknown;
        manifest?: { job_id: string };
        output_dir?: string;
      }>(r);
      if (!r.ok) {
        throw new Error(formatApiDetail(data.detail));
      }
      setPackResult({
        job_id: data.manifest?.job_id ?? "?",
        output_dir: data.output_dir ?? "",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPackLoading(false);
    }
  }

  async function onRunJob() {
    if (!STUDIO_API_READY) {
      setError("Worker URL is not configured.");
      return;
    }
    setJobLoading(true);
    setError(null);
    setPackResult(null);
    setJobResult(null);
    try {
      // Enqueue + poll: Cloudflare Worker → origin fetch times out on long synchronous /jobs/run
      // (textures + mesh). Short requests stay under proxy limits.
      const idem =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `web-${Date.now()}`;
      const enqRes = await fetch(`${STUDIO_API_BASE}/api/studio/queue/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          prompt,
          category,
          style_preset: stylePreset,
          mock,
          generate_textures: generateTextures,
          export_mesh: exportMesh,
          unity_urp_hint: "6000.0.x LTS (pin when smoke-tested)",
          max_attempts: 3,
          idempotency_key: idem,
        }),
      });
      const enq = await readApiJson<{ queue_id?: string; detail?: unknown }>(enqRes);
      if (!enqRes.ok) {
        throw new Error(formatApiDetail(enq.detail));
      }
      const queueId = enq.queue_id;
      if (!queueId) {
        throw new Error("Enqueue response missing queue_id");
      }

      const deadline = Date.now() + STUDIO_QUEUE_MAX_WAIT_MS;
      let lastStatus = "unknown";
      while (Date.now() < deadline) {
        const pr = await fetch(`${STUDIO_API_BASE}/api/studio/queue/jobs/${queueId}`, {
          headers: authHeaders(),
        });
        const row = await readApiJson<QueueJobRow & { detail?: unknown }>(pr);
        if (!pr.ok) {
          throw new Error(formatApiDetail(row.detail));
        }
        lastStatus = row.status;
        if (row.status === "completed") {
          const data = row.result;
          if (!data) {
            throw new Error("Job completed without result payload");
          }
          setSpec(data.spec ?? null);
          setJobResult({
            job_id: data.job_id ?? "?",
            zip_path: data.zip_path ?? "",
            errors: data.errors ?? [],
            texture_logs: data.texture_logs ?? [],
            mesh_logs: data.mesh_logs ?? [],
          });
          refreshJobs();
          return;
        }
        if (row.status === "dead") {
          throw new Error(row.last_error?.trim() || "Job failed (dead letter)");
        }
        await new Promise((res) => window.setTimeout(res, STUDIO_QUEUE_POLL_MS));
      }
      throw new Error(
        `Timed out after ${STUDIO_QUEUE_MAX_WAIT_MS / 60000} minutes waiting for job ${queueId} (last status: ${lastStatus})`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setJobLoading(false);
    }
  }

  async function startStripeCheckout(tier: "indie" | "team") {
    if (!STUDIO_API_READY) {
      return;
    }
    setError(null);
    try {
      const r = await fetch(`${STUDIO_API_BASE}/api/studio/billing/checkout-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ tier }),
      });
      const data = await readApiJson<{ url?: string; detail?: unknown }>(r);
      if (!r.ok) {
        throw new Error(formatApiDetail(data.detail));
      }
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function openStripePortal() {
    if (!STUDIO_API_READY) {
      return;
    }
    setError(null);
    try {
      const r = await fetch(`${STUDIO_API_BASE}/api/studio/billing/portal-session`, {
        method: "POST",
        headers: authHeaders(),
      });
      const data = await readApiJson<{ url?: string; detail?: unknown }>(r);
      if (!r.ok) {
        throw new Error(formatApiDetail(data.detail));
      }
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function downloadJobZip(jobId: string) {
    if (!STUDIO_API_READY) {
      setError("Worker URL is not configured.");
      return;
    }
    try {
      const r = await fetch(`${STUDIO_API_BASE}/api/studio/jobs/${jobId}/download`, {
        headers: authHeaders(),
      });
      if (!r.ok) {
        const errBody = (await r.json().catch(() => null)) as { detail?: unknown } | null;
        throw new Error(formatApiDetail(errBody?.detail ?? r.statusText));
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `immersive-studio-${jobId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const texturesBlocked = Boolean(usage?.limits_enforced && !usage.textures_allowed);

  return (
    <>
      <EngravedBackdrop />
      <div className="page studio-page">
        <header className="header">
          <Link className="logo" to="/">
            <img className="logo-mark-img" src="/brand-mark.png" alt="" width={32} height={32} />
            Immersive Labs
          </Link>
          <nav className="nav" aria-label="Primary">
            <Link to="/">Home</Link>
            <Link to="/studio" className="nav-active">
              Game studio
            </Link>
            <Link to="/docs">Docs</Link>
          </nav>
        </header>

        <main className="studio-main">
          <p className="eyebrow">Video Game Generation Studio</p>
          <h1 className="studio-title">Pipeline</h1>
          <p className="studio-lede">
            Generate a validated <code>StudioAssetSpec</code>, run a full persisted <strong>job</strong> (pack + zip +
            index), optionally invoke <strong>ComfyUI</strong> for albedo textures, then import in Unity via{" "}
            <code>packages/studio-unity</code>. Start with the on-site{" "}
            <Link to="/docs">documentation hub</Link> (overview, deployment, ComfyUI, Blender, Unity); deep reference:{" "}
            <code className="studio-code-inline">docs/studio/essentials.md</code> and{" "}
            <code className="studio-code-inline">docs/studio/platform-manual.md</code>.
          </p>
          <p className="studio-cli-hint">
            Install the open-source CLI from{" "}
            <a href="https://pypi.org/project/immersive-studio/" target="_blank" rel="noopener noreferrer">
              PyPI
            </a>
            : <code>pipx install immersive-studio</code> or <code>pip install immersive-studio</code>.
          </p>

          {!STUDIO_API_READY ? (
            <div className="studio-health studio-health--error studio-config-banner" role="alert">
              <strong>Worker URL is not configured for this build.</strong> The browser cannot call{" "}
              <code>127.0.0.1:8787</code> from a deployed site or from another machine. Set{" "}
              <code>VITE_STUDIO_API_URL</code> to your public worker base URL (no trailing slash), then rebuild.
              <br />
              <span className="studio-config-banner-sub">
                <strong>Vercel:</strong> Project → Settings → Environment Variables → add{" "}
                <code>VITE_STUDIO_API_URL</code> = <code>https://your-worker.example.com</code> → redeploy.
                <br />
                <strong>Local dev:</strong> run <code>npm run dev</code> (defaults to{" "}
                <code>http://127.0.0.1:8787</code>) or put the same value in{" "}
                <code>apps/web/.env.development.local</code>.
              </span>
            </div>
          ) : (
            <div className={`studio-health studio-health--${health}`} role="status">
              {health === "checking" && "Checking worker…"}
              {health === "ok" && <>Worker reachable at {studioWorkerDisplayOrigin()}</>}
              {health === "error" && (
                <>
                  Worker not reachable at {studioWorkerDisplayOrigin()}.{" "}
                  {import.meta.env.PROD ? (
                    <>
                      This is the public API URL baked into the site at build time — it is not your laptop. Fix the
                      server, tunnel, or <code>ORIGIN_URL</code> behind <code>{studioWorkerDisplayOrigin()}</code> (see{" "}
                      <code>apps/studio-edge/README.md</code>), then redeploy only if you change{" "}
                      <code>VITE_STUDIO_API_URL</code>.
                    </>
                  ) : (
                    <>
                      Run <code>immersive-studio serve --host 127.0.0.1 --port 8787</code> from{" "}
                      <code>apps/studio-worker</code>, or fix <code>VITE_STUDIO_API_URL</code> /{" "}
                      <code>VITE_STUDIO_API_PROXY</code> in <code>apps/web/.env.development.local</code>.
                    </>
                  )}{" "}
                  <button type="button" className="studio-retry" onClick={checkHealth}>
                    Retry
                  </button>
                  {healthErrorHint ? (
                    <span className="studio-config-banner-sub">
                      <br />
                      {healthErrorHint}
                    </span>
                  ) : null}
                </>
              )}
            </div>
          )}

          <div className="studio-api-key">
            <label className="studio-label">
              API key (shared studio / remote server)
              <input
                className="studio-input"
                type="password"
                autoComplete="off"
                placeholder={
                  authRequired ? "Required — paste key from immersive-studio tenants issue-key" : "Optional if server uses local dev mode"
                }
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </label>
            <div className="studio-api-key-actions">
              <button type="button" className="btn btn-ghost" onClick={persistApiKey}>
                Save in browser
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={!STUDIO_API_READY}
                onClick={() => {
                  refreshUsage();
                  refreshJobs();
                  refreshBilling();
                }}
              >
                Refresh usage & jobs
              </button>
            </div>
            {authRequired && !apiKey.trim() ? (
              <p className="studio-api-key-warn">
                This worker requires an API key (operator set <code>STUDIO_API_AUTH_REQUIRED=1</code>).
              </p>
            ) : null}
            {usage ? (
              <p className="studio-usage" role="status">
                <strong>Plan:</strong> {usage.tier_name} ({usage.tier_id}
                {usage.limits_enforced && usage.credits_cap != null
                  ? `) — credits ${usage.credits_used} / ${usage.credits_cap} this month`
                  : ") — local dev limits off"}
                {usage.limits_enforced ? (
                  <>
                    {" "}
                    · textures {usage.textures_allowed ? "allowed" : "not included"}
                    {usage.max_concurrent_jobs != null ? ` · max ${usage.max_concurrent_jobs} concurrent jobs` : null}
                  </>
                ) : null}
              </p>
            ) : null}
            {billing?.stripe_checkout_available && usage?.limits_enforced ? (
              <div className="studio-billing">
                <p className="studio-billing-title">Stripe billing</p>
                <p className="studio-billing-hint">
                  Opens Stripe Checkout. After payment, webhooks update your tier automatically.
                </p>
                <div className="studio-billing-actions">
                  {billing.checkout_tiers.includes("indie") ? (
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => void startStripeCheckout("indie")}
                    >
                      Subscribe — Indie
                    </button>
                  ) : null}
                  {billing.checkout_tiers.includes("team") ? (
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => void startStripeCheckout("team")}
                    >
                      Subscribe — Small team
                    </button>
                  ) : null}
                  {billing.stripe_customer_linked ? (
                    <button type="button" className="btn btn-primary" onClick={() => void openStripePortal()}>
                      Manage billing
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>

          {comfy ? (
            <div
              className={`studio-health ${
                comfy.reachable ? "studio-health--ok" : "studio-health--optional"
              }`}
              role="status"
            >
              ComfyUI
              {comfy.url ? (
                <>
                  {" "}
                  at <code>{comfy.url}</code>
                </>
              ) : (
                <>
                  {" "}
                  (Comfy status unavailable — the Studio API request failed; fix worker health above before tuning
                  Comfy.)
                </>
              )}
              : {comfy.reachable ? "reachable" : "not running"}
              {comfy.detail ? ` — ${comfy.detail}` : null}
              {!comfy.reachable ? (
                <span className="studio-comfy-hint">
                  {" "}
                  {comfyLocalhostRefused(comfy.detail, comfy.url) ? (
                    <>
                      <strong>No process on port 8188.</strong> Start ComfyUI in a <em>second</em> terminal (not this
                      repo): <code>python main.py --listen 127.0.0.1 --port 8188</code> from your{" "}
                      <a href="https://github.com/comfyanonymous/ComfyUI" target="_blank" rel="noopener noreferrer">
                        ComfyUI
                      </a>{" "}
                      install, then click Refresh. Guide: <code>scripts/local-pc-studio/README.md</code> §3.
                    </>
                  ) : (
                    <>
                      (optional — only if you enable <strong>Generate albedo textures</strong>. Set{" "}
                      <code>STUDIO_COMFY_URL</code> on the worker, e.g.{" "}
                      <code>https://comfy.immersivelabs.space</code>, or run ComfyUI locally on port 8188.)
                    </>
                  )}
                </span>
              ) : null}
              <button type="button" className="studio-retry" onClick={refreshComfy}>
                Refresh
              </button>
            </div>
          ) : null}

          {jobsRoot ? (
            <p className="studio-jobs-root">
              Jobs folder: <code>{jobsRoot}</code>
            </p>
          ) : null}

          <section className="studio-queue-hint" aria-labelledby="queue-hint-title">
            <h3 id="queue-hint-title" className="studio-queue-hint-title">
              Async queue (optional)
            </h3>
            <p className="studio-queue-hint-body">
              POST <code>/api/studio/queue/jobs</code> with the same fields as a full job. Send{" "}
              <code>idempotency_key</code> (≤128 chars) to reuse an existing <code>queue_id</code> without spending
              credits again. Response includes <code>deduplicated: true</code> when matched.
            </p>
          </section>

          <form
            className="studio-form"
            onSubmit={onGenerate}
            aria-busy={loading || jobLoading || packLoading}
          >
            <label className="studio-label">
              Creative brief
              <textarea
                className="studio-input studio-textarea"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={4}
                placeholder="e.g. Wooden crate with iron bands, slightly worn…"
                required
              />
            </label>

            <div className="studio-row">
              <label className="studio-label">
                Category
                <select
                  className="studio-input"
                  value={category}
                  onChange={(e) => setCategory(e.target.value as StudioCategory)}
                >
                  <option value="prop">prop</option>
                  <option value="environment_piece">environment_piece</option>
                  <option value="character_base">character_base</option>
                  <option value="material_library">material_library</option>
                </select>
              </label>
              <label className="studio-label">
                Style preset
                <select
                  className="studio-input"
                  value={stylePreset}
                  onChange={(e) => setStylePreset(e.target.value as StudioStyle)}
                >
                  <option value="toon_bold">toon_bold</option>
                  <option value="anime_stylized">anime_stylized</option>
                  <option value="realistic_hd_pbr">realistic_hd_pbr</option>
                </select>
              </label>
            </div>

            <label className="studio-check">
              <input type="checkbox" checked={mock} onChange={(e) => setMock(e.target.checked)} />
              Mock mode (no Ollama — deterministic spec for wiring)
            </label>

            <label className="studio-check">
              <input
                type="checkbox"
                checked={generateTextures}
                disabled={texturesBlocked}
                onChange={(e) => setGenerateTextures(e.target.checked)}
              />
              Generate albedo textures via ComfyUI (requires running ComfyUI + checkpoint env — see worker README)
              {texturesBlocked ? (
                <span className="studio-check-note"> — not included on your current plan.</span>
              ) : null}
            </label>

            <label className="studio-check">
              <input type="checkbox" checked={exportMesh} onChange={(e) => setExportMesh(e.target.checked)} />
              Export placeholder mesh (Blender GLB — set{" "}
              <code>STUDIO_BLENDER_BIN</code> or install Blender on PATH)
            </label>

            <div className="studio-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading || !STUDIO_API_READY}
              >
                {loading ? "Generating…" : "Generate spec"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={!spec || packLoading || !STUDIO_API_READY}
                onClick={() => void onWritePack()}
              >
                {packLoading ? "Writing pack…" : "Write pack (ad-hoc)"}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={jobLoading || !prompt.trim() || !STUDIO_API_READY}
                onClick={() => void onRunJob()}
              >
                {jobLoading ? "Running job…" : "Run full job"}
              </button>
            </div>
          </form>

          {error ? <pre className="studio-error">{error}</pre> : null}

          {meta ? (
            <p className="studio-meta">
              <strong>Meta:</strong> <code>{JSON.stringify(meta)}</code>
            </p>
          ) : null}

          {spec ? (
            <pre className="studio-json" tabIndex={0}>
              {JSON.stringify(spec, null, 2)}
            </pre>
          ) : null}

          {packResult ? (
            <p className="studio-pack-result">
              Pack written. Job <code>{packResult.job_id}</code>
              <br />
              <code className="studio-path">{packResult.output_dir}</code>
            </p>
          ) : null}

          {jobResult ? (
            <div className="studio-job-result">
              <p>
                Job <code>{jobResult.job_id}</code> — zip: <code className="studio-path">{jobResult.zip_path}</code>
              </p>
              {jobResult.errors.length > 0 ? (
                <p className="studio-job-warn">Job reported issues: {jobResult.errors.join(" · ")}</p>
              ) : null}
              {jobResult.texture_logs.length > 0 ? (
                <details className="studio-log-details">
                  <summary>Texture pipeline log ({jobResult.texture_logs.length} lines)</summary>
                  <ul className="studio-log-list">
                    {jobResult.texture_logs.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </details>
              ) : null}
              {jobResult.mesh_logs.length > 0 ? (
                <details className="studio-log-details">
                  <summary>Mesh export log ({jobResult.mesh_logs.length} lines)</summary>
                  <ul className="studio-log-list">
                    {jobResult.mesh_logs.map((line) => (
                      <li key={`mesh-${line}`}>{line}</li>
                    ))}
                  </ul>
                </details>
              ) : null}
              <button
                type="button"
                className="btn btn-primary studio-download"
                disabled={!STUDIO_API_READY}
                onClick={() => void downloadJobZip(jobResult.job_id)}
              >
                Download pack.zip
              </button>
            </div>
          ) : null}

          <section className="studio-jobs" aria-labelledby="jobs-heading">
            <div className="studio-jobs-header">
              <h2 id="jobs-heading" className="studio-jobs-title">
                Recent jobs
              </h2>
              <button type="button" className="studio-retry" disabled={!STUDIO_API_READY} onClick={refreshJobs}>
                Refresh now
              </button>
            </div>
            {jobs.length === 0 ? (
              <p className="studio-jobs-empty">No jobs yet. Run a full job to populate the index.</p>
            ) : (
              <div className="studio-table-wrap">
                <table className="studio-table">
                  <thead>
                    <tr>
                      <th scope="col">Created</th>
                      <th scope="col">Summary</th>
                      <th scope="col">Status</th>
                      <th scope="col">Textures</th>
                      <th scope="col">Download</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((j) => (
                      <tr key={j.job_id}>
                        <td>
                          <code className="studio-table-mono">{j.created_at}</code>
                        </td>
                        <td>
                          <code>{j.summary}</code>
                          <div className="studio-table-sub">{j.job_id}</div>
                        </td>
                        <td>
                          {j.status}
                          {j.error ? <div className="studio-table-err">{j.error}</div> : null}
                        </td>
                        <td>{j.has_textures ? "yes" : "no"}</td>
                        <td>
                          <button
                            type="button"
                            className="studio-table-link"
                            disabled={!STUDIO_API_READY}
                            onClick={() => void downloadJobZip(j.job_id)}
                          >
                            ZIP
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </main>

        <footer className="footer">
          <span>© {new Date().getFullYear()} Immersive Labs</span>
            <span className="footer-meta">
            <Link to="/">Marketing site</Link>
            <span> · </span>
            <code>docs/studio/essentials.md</code>
          </span>
        </footer>
      </div>
    </>
  );
}
