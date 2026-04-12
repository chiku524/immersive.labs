/**
 * Worker base URL for Studio API calls.
 *
 * - Production builds must set VITE_STUDIO_API_URL at build time (e.g. Vercel env).
 * - Local dev: unset → http://127.0.0.1:8787 (direct; set STUDIO_CORS_ORIGINS on the worker).
 * - Local dev: VITE_STUDIO_API_PROXY=1 → "" (same-origin `/api/studio/*`; Vite proxies to 8787).
 */
function resolveStudioApiBase(): string {
  const raw = import.meta.env.VITE_STUDIO_API_URL;
  if (typeof raw === "string" && raw.trim()) {
    return raw.trim().replace(/\/$/, "");
  }
  if (import.meta.env.DEV && import.meta.env.VITE_STUDIO_API_PROXY === "1") {
    return "";
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
