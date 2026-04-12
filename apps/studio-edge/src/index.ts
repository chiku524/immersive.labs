/**
 * Studio edge Worker: proxy all traffic to the Python studio API origin.
 * Optional KV binding `STUDIO_KV` caches GET /api/studio/health for a few seconds.
 *
 * CORS: upstream FastAPI sets ACAO when healthy, but 502/HTML error pages and Worker
 * catch paths often omit it — browsers then report a CORS failure. We answer OPTIONS
 * here and inject ACAO on responses when Origin is in STUDIO_CORS_ORIGINS.
 */

const HEALTH_PATH = "/api/studio/health";
const HEALTH_KV_KEY = "studio:health:v1";
const HEALTH_KV_TTL_SECONDS = 60;

export interface Env {
  ORIGIN_URL: string;
  /** Comma-separated browser origins (scheme + host, no path). Mirrors STUDIO_CORS_ORIGINS on the Python worker. */
  STUDIO_CORS_ORIGINS?: string;
  /** Milliseconds; optional wrangler var, default 5000 */
  HEALTH_CACHE_TTL_MS?: string;
  /** Optional — enable short-lived health cache */
  STUDIO_KV?: KVNamespace;
  /** R2 bucket for edge-native objects (Python job artifacts may use a separate bucket via S3 API). */
  STUDIO_R2: R2Bucket;
  /** D1 for edge-only metadata (not shared with Python SQLite). */
  STUDIO_D1: D1Database;
}

function originBase(env: Env): string {
  const raw = (env.ORIGIN_URL ?? "").trim();
  if (!raw) {
    throw new Error("ORIGIN_URL is not set");
  }
  return raw.replace(/\/$/, "");
}

/** Hostname only — helps verify Worker → origin wiring (see README / tunnel DNS). */
function originHostname(env: Env): string {
  try {
    return new URL(originBase(env)).hostname;
  } catch {
    return "?";
  }
}

function healthCacheTtlMs(env: Env): number {
  const raw = env.HEALTH_CACHE_TTL_MS ?? "5000";
  const n = Number.parseInt(String(raw), 10);
  return Number.isFinite(n) && n >= 0 ? Math.min(n, 60_000) : 5000;
}

/** Same shape as studio_worker.api._cors_allow_origins defaults + production marketing origins. */
function parseCorsOrigins(env: Env): string[] {
  const raw = (env.STUDIO_CORS_ORIGINS ?? "").trim();
  if (raw === "*") {
    return ["*"];
  }
  if (!raw) {
    return [
      "https://www.immersivelabs.space",
      "https://immersivelabs.space",
      "https://immersivelabs.vercel.app",
      "https://immersive-studio-edge.nico-chikuji.workers.dev",
      "http://127.0.0.1:5173",
      "http://localhost:5173",
    ];
  }
  const out: string[] = [];
  for (const o of raw.split(",")) {
    const x = o.trim().replace(/\/$/, "");
    if (x) {
      out.push(x);
    }
  }
  return out;
}

function normalizeOrigin(origin: string | null): string {
  return (origin ?? "").trim().replace(/\/$/, "");
}

function pickAllowOrigin(request: Request, allowed: string[]): string | null {
  const origin = normalizeOrigin(request.headers.get("Origin"));
  if (!origin) {
    return null;
  }
  if (allowed.includes("*")) {
    return "*";
  }
  return allowed.includes(origin) ? origin : null;
}

function corsPreflightHeaders(request: Request, allowOrigin: string): Headers {
  const h = new Headers();
  h.set("Access-Control-Allow-Origin", allowOrigin);
  h.set("Access-Control-Allow-Credentials", "true");
  h.set("Access-Control-Allow-Methods", "GET,HEAD,POST,PUT,PATCH,DELETE,OPTIONS");
  const reqHdrs = request.headers.get("Access-Control-Request-Headers");
  if (reqHdrs) {
    h.set("Access-Control-Allow-Headers", reqHdrs);
  } else {
    h.set("Access-Control-Allow-Headers", "Authorization, Content-Type");
  }
  h.set("Access-Control-Max-Age", "86400");
  return h;
}

function mergeCors(request: Request, response: Response, allowed: string[]): Response {
  const o = pickAllowOrigin(request, allowed);
  if (!o || o === "*") {
    return response;
  }
  const headers = new Headers(response.headers);
  if (!headers.has("Access-Control-Allow-Origin")) {
    headers.set("Access-Control-Allow-Origin", o);
    headers.set("Access-Control-Allow-Credentials", "true");
    const vary = headers.get("Vary");
    if (!vary) {
      headers.set("Vary", "Origin");
    } else if (!vary.split(",").map((x) => x.trim()).includes("Origin")) {
      headers.set("Vary", `${vary}, Origin`);
    }
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

/** Strip headers that should not be blindly forwarded to origin. */
function scrubRequestHeaders(incoming: Headers): Headers {
  const out = new Headers(incoming);
  const drop = [
    "host",
    "cf-connecting-ip",
    "cf-ipcountry",
    "cf-ray",
    "cf-visitor",
    "x-forwarded-host",
    "x-forwarded-proto",
  ];
  for (const k of drop) {
    out.delete(k);
  }
  return out;
}

async function proxyToOrigin(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const target = `${originBase(env)}${url.pathname}${url.search}`;
  const headers = scrubRequestHeaders(request.headers);
  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
  }
  return fetch(new Request(target, init));
}

/**
 * Cloudflare / tunnel often answer 5xx with an HTML error page. The /studio UI expects JSON;
 * rewrite so readApiJson shows a structured detail instead of "Unexpected token '<'".
 */
async function coerceJsonForStudioApiHtmlErrors(
  request: Request,
  proxied: Response,
): Promise<Response> {
  const url = new URL(request.url);
  if (!url.pathname.startsWith("/api/studio/")) {
    return proxied;
  }
  if (proxied.status < 500 || proxied.status > 599) {
    return proxied;
  }
  const ct = (proxied.headers.get("content-type") || "").toLowerCase();
  if (!ct.includes("text/html") && !ct.includes("text/plain")) {
    return proxied;
  }
  const text = await proxied.text();
  const t = text.trimStart();
  if (!t.startsWith("<!") && !t.toLowerCase().startsWith("<html")) {
    return new Response(text, {
      status: proxied.status,
      statusText: proxied.statusText,
      headers: proxied.headers,
    });
  }
  const body = JSON.stringify({
    detail:
      "Gateway or tunnel returned HTML instead of JSON (origin unreachable, overloaded, or timed out).",
    gateway_status: proxied.status,
  });
  return new Response(body, {
    status: proxied.status,
    statusText: proxied.statusText,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

async function cachedHealth(request: Request, env: Env): Promise<Response | null> {
  const kv = env.STUDIO_KV;
  if (!kv) {
    return null;
  }
  const ttlMs = healthCacheTtlMs(env);
  const raw = await kv.get(HEALTH_KV_KEY);
  if (!raw) {
    return null;
  }
  let entry: { t: number; body: unknown; acao: string | null };
  try {
    entry = JSON.parse(raw) as { t: number; body: unknown; acao: string | null };
  } catch {
    return null;
  }
  if (typeof entry.t !== "number" || Date.now() - entry.t > ttlMs) {
    return null;
  }
  const allowed = parseCorsOrigins(env);
  const headers = new Headers({
    "Content-Type": "application/json",
    "X-Studio-Edge-Cache": "HIT",
    "X-Studio-Edge-Origin-Host": originHostname(env),
  });
  const o = pickAllowOrigin(request, allowed);
  if (o) {
    headers.set("Access-Control-Allow-Origin", o);
    headers.set("Access-Control-Allow-Credentials", "true");
  } else if (entry.acao) {
    headers.set("Access-Control-Allow-Origin", entry.acao);
    headers.set("Access-Control-Allow-Credentials", "true");
  }
  return new Response(JSON.stringify(entry.body), { status: 200, headers });
}

async function fetchAndStoreHealth(request: Request, env: Env, kv: KVNamespace): Promise<Response> {
  const target = `${originBase(env)}${HEALTH_PATH}`;
  const headers = scrubRequestHeaders(request.headers);
  const upstream = await fetch(new Request(target, { method: "GET", headers, redirect: "manual" }));
  const text = await upstream.text();
  let bodyJson: unknown;
  try {
    bodyJson = JSON.parse(text) as unknown;
  } catch {
    const allowed = parseCorsOrigins(env);
    const out = new Headers(upstream.headers);
    out.set("X-Studio-Edge-Cache", "MISS");
    const r = new Response(text, { status: upstream.status, statusText: upstream.statusText, headers: out });
    return mergeCors(request, r, allowed);
  }
  const acao = upstream.headers.get("Access-Control-Allow-Origin");
  await kv.put(
    HEALTH_KV_KEY,
    JSON.stringify({ t: Date.now(), body: bodyJson, acao }),
    { expirationTtl: HEALTH_KV_TTL_SECONDS },
  );
  const allowed = parseCorsOrigins(env);
  const out = new Headers(upstream.headers);
  out.set("X-Studio-Edge-Cache", "MISS");
  out.set("X-Studio-Edge-Origin-Host", originHostname(env));
  const r = new Response(JSON.stringify(bodyJson), { status: upstream.status, headers: out });
  return mergeCors(request, r, allowed);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const allowed = parseCorsOrigins(env);

    if (request.method === "OPTIONS") {
      const o = pickAllowOrigin(request, allowed);
      if (!o) {
        return new Response(null, { status: 204 });
      }
      return new Response(null, { status: 204, headers: corsPreflightHeaders(request, o) });
    }

    try {
      const url = new URL(request.url);
      if (request.method === "GET" && url.pathname === HEALTH_PATH && env.STUDIO_KV) {
        const hit = await cachedHealth(request, env);
        if (hit) {
          return hit;
        }
        return fetchAndStoreHealth(request, env, env.STUDIO_KV);
      }
      const proxied = await proxyToOrigin(request, env);
      const normalized = await coerceJsonForStudioApiHtmlErrors(request, proxied);
      const withOriginHint = new Response(normalized.body, {
        status: normalized.status,
        statusText: normalized.statusText,
        headers: (() => {
          const h = new Headers(normalized.headers);
          h.set("X-Studio-Edge-Origin-Host", originHostname(env));
          return h;
        })(),
      });
      return mergeCors(request, withOriginHint, allowed);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      const o = pickAllowOrigin(request, allowed);
      const headers = new Headers({ "Content-Type": "application/json" });
      if (o) {
        headers.set("Access-Control-Allow-Origin", o);
        headers.set("Access-Control-Allow-Credentials", "true");
      }
      return new Response(JSON.stringify({ error: "studio-edge", detail: msg }), {
        status: 502,
        headers,
      });
    }
  },
};
