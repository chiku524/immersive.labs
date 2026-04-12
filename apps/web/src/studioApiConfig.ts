/**
 * Worker base URL for Studio API calls.
 *
 * - Production builds must set VITE_STUDIO_API_URL at build time (e.g. Vercel env).
 * - Local dev: unset → http://127.0.0.1:8787 (direct; set STUDIO_CORS_ORIGINS on the worker).
 * - Local dev: VITE_STUDIO_API_PROXY=1 → "" (same-origin `/api/studio/*`; Vite proxies to 8787).
 */
function resolveStudioApiBase(): string {
  // In dev, proxy mode must win over VITE_STUDIO_API_URL — many machines have a production URL in `.env`
  // for `vite build` / preview; that would break `npm run dev` + same-origin proxy.
  if (import.meta.env.DEV && import.meta.env.VITE_STUDIO_API_PROXY === "1") {
    return "";
  }
  const raw = import.meta.env.VITE_STUDIO_API_URL;
  if (typeof raw === "string" && raw.trim()) {
    return raw.trim().replace(/\/$/, "");
  }
  if (import.meta.env.DEV) {
    return "http://127.0.0.1:8787";
  }
  return "";
}

export const STUDIO_API_BASE = resolveStudioApiBase();

export const STUDIO_API_READY =
  STUDIO_API_BASE.length > 0 ||
  (Boolean(import.meta.env.DEV) && import.meta.env.VITE_STUDIO_API_PROXY === "1");

/** Human-readable origin for /studio status lines (never empty in dev when proxy is on). */
export function studioWorkerDisplayOrigin(): string {
  if (STUDIO_API_BASE) {
    return STUDIO_API_BASE;
  }
  if (import.meta.env.DEV && import.meta.env.VITE_STUDIO_API_PROXY === "1") {
    return "this dev server (Vite → 127.0.0.1:8787)";
  }
  return "local worker";
}
