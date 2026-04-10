/**
 * Studio edge Worker: proxy all traffic to the Python studio API origin.
 * Optional KV binding `STUDIO_KV` caches GET /api/studio/health for a few seconds.
 */

const HEALTH_PATH = "/api/studio/health";
const HEALTH_KV_KEY = "studio:health:v1";
const HEALTH_KV_TTL_SECONDS = 60;

export interface Env {
  ORIGIN_URL: string;
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

function healthCacheTtlMs(env: Env): number {
  const raw = env.HEALTH_CACHE_TTL_MS ?? "5000";
  const n = Number.parseInt(String(raw), 10);
  return Number.isFinite(n) && n >= 0 ? Math.min(n, 60_000) : 5000;
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
  const headers = new Headers({
    "Content-Type": "application/json",
    "X-Studio-Edge-Cache": "HIT",
  });
  if (entry.acao) {
    headers.set("Access-Control-Allow-Origin", entry.acao);
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
    const out = new Headers(upstream.headers);
    out.set("X-Studio-Edge-Cache", "MISS");
    return new Response(text, { status: upstream.status, statusText: upstream.statusText, headers: out });
  }
  const acao = upstream.headers.get("Access-Control-Allow-Origin");
  await kv.put(
    HEALTH_KV_KEY,
    JSON.stringify({ t: Date.now(), body: bodyJson, acao }),
    { expirationTtl: HEALTH_KV_TTL_SECONDS },
  );
  const out = new Headers(upstream.headers);
  out.set("X-Studio-Edge-Cache", "MISS");
  return new Response(JSON.stringify(bodyJson), { status: upstream.status, headers: out });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      const url = new URL(request.url);
      if (request.method === "GET" && url.pathname === HEALTH_PATH && env.STUDIO_KV) {
        const hit = await cachedHealth(request, env);
        if (hit) {
          return hit;
        }
        return fetchAndStoreHealth(request, env, env.STUDIO_KV);
      }
      return await proxyToOrigin(request, env);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return new Response(JSON.stringify({ error: "studio-edge", detail: msg }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      });
    }
  },
};
