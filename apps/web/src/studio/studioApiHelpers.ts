/** Shared Studio API helpers (gateway detection, JSON parse, transient retries). */

export function isGatewayDetailMessage(msg: string): boolean {
  return (
    /Gateway or tunnel returned HTTP/i.test(msg) ||
    /gateway_status/i.test(msg) ||
    /invalid JSON.*502/i.test(msg)
  );
}

export function formatApiDetail(detail: unknown): string {
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
export async function readApiJson<T>(r: Response): Promise<T> {
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

/** Tunnel / origin often returns transient 5xx when the VM is busy (e.g. Ollama + Comfy). */
export const RETRYABLE_HTTP = new Set([502, 503, 504, 524, 530]);

export function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

export function delay(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const t = window.setTimeout(() => resolve(), ms);
    const onAbort = () => {
      window.clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export async function fetchWithTransientRetry(
  url: string,
  init: RequestInit,
  maxAttempts = 3,
): Promise<Response> {
  const signal = init.signal ?? undefined;
  let last: Response | undefined;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    if (attempt > 0) {
      await delay(400 * attempt, signal);
    }
    last = await fetch(url, init);
    if (last.ok || !RETRYABLE_HTTP.has(last.status)) {
      break;
    }
  }
  return last as Response;
}
