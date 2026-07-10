/** Queue job SSE + polling transport for Studio. */

import { STUDIO_API_BASE } from "../studioApiConfig";
import {
  delay,
  fetchWithTransientRetry,
  formatApiDetail,
  isAbortError,
  isGatewayDetailMessage,
  readApiJson,
  RETRYABLE_HTTP,
} from "./studioApiHelpers";

export const STUDIO_QUEUE_POLL_MS = 2000;
/** Must cover long Comfy + LLM runs after SSE closes (see STUDIO_QUEUE_SSE_MAX_DURATION_S on the worker). */
export const STUDIO_QUEUE_MAX_WAIT_MS = 120 * 60 * 1000;

/** How many times to retry SSE before falling back to GET polling. */
const SSE_RECONNECT_ATTEMPTS = 2;

export type QueueTransportMode = "sse" | "polling";

export class SseTransportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SseTransportError";
  }
}

export type QueueJobRow = {
  status: string;
  last_error?: string | null;
  /** In-flight pipeline step (e.g. Comfy textures) while status is running. */
  progress?: {
    phase?: string;
    done?: number;
    total?: number;
    label?: string;
    width?: number;
    height?: number;
  } | null;
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

/**
 * ``GET …/queue/jobs/{id}/events`` (``text/event-stream``) with ``Authorization`` — EventSource cannot set headers.
 * Throws {@link SseTransportError} for proxy/stream issues so the caller can fall back to GET polling.
 */
export async function consumeQueueJobSse(
  eventsUrl: string,
  auth: Record<string, string>,
  signal: AbortSignal,
  onProgress?: (row: QueueJobRow) => void,
): Promise<QueueJobRow> {
  let res: Response;
  try {
    res = await fetch(eventsUrl, {
      method: "GET",
      headers: { Accept: "text/event-stream", ...auth },
      signal,
      cache: "no-store",
    });
  } catch (e) {
    if (signal.aborted || isAbortError(e)) {
      throw e;
    }
    throw new SseTransportError(e instanceof Error ? e.message : "fetch failed");
  }
  if (res.status === 401 || res.status === 403) {
    const t = await res.text();
    throw new Error(
      res.status === 401
        ? "Unauthorized (check Studio API key)."
        : `Forbidden: ${t.slice(0, 200)}`,
    );
  }
  if (!res.ok) {
    throw new SseTransportError(`SSE endpoint HTTP ${res.status}`);
  }
  const ct = (res.headers.get("content-type") || "").toLowerCase();
  if (!ct.includes("text/event-stream")) {
    throw new SseTransportError(`Expected text/event-stream, got ${ct || "(empty)"}`);
  }
  if (!res.body) {
    throw new SseTransportError("SSE response has no body");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let eventName = "message";
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith(":")) {
          continue;
        }
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trimStart());
        }
      }
      const dataStr = dataLines.join("\n");
      if (!dataStr) {
        continue;
      }
      if (eventName === "error") {
        let detail = dataStr;
        try {
          const j = JSON.parse(dataStr) as { detail?: unknown };
          if (typeof j.detail === "string") {
            detail = j.detail;
          }
        } catch {
          /* use raw */
        }
        if (isGatewayDetailMessage(detail)) {
          throw new SseTransportError(detail);
        }
        throw new Error(detail);
      }
      if (eventName === "job") {
        let row: QueueJobRow;
        try {
          row = JSON.parse(dataStr) as QueueJobRow;
        } catch {
          throw new SseTransportError("Invalid job JSON in SSE payload");
        }
        if (row.status === "completed") {
          return row;
        }
        if (row.status === "dead") {
          throw new Error(row.last_error?.trim() || "Job failed (dead letter)");
        }
        if (onProgress && (row.status === "running" || row.status === "pending")) {
          onProgress(row);
        }
      }
    }
  }
  throw new SseTransportError("SSE stream closed before job reached a terminal status");
}

export function formatQueueJobProgress(row: QueueJobRow): string | null {
  const p = row.progress;
  if (p && typeof p.done === "number" && typeof p.total === "number" && p.total > 0) {
    const w = p.width && p.height ? ` · ${p.width}×${p.height}` : "";
    return `Textures ${p.done}/${p.total}${p.label ? ` · ${p.label}` : ""}${w}`;
  }
  if (row.status === "running") {
    return "Running on worker…";
  }
  if (row.status === "pending") {
    return "Queued…";
  }
  return null;
}

/** Background SSE watch for dashboard rows (does not block the active job runner). */
export async function watchQueueJobSse(
  queueId: string,
  auth: Record<string, string>,
  signal: AbortSignal,
  onUpdate: (row: QueueJobRow) => void,
): Promise<void> {
  const eventsUrl = `${STUDIO_API_BASE}/api/studio/queue/jobs/${encodeURIComponent(queueId)}/events`;
  try {
    const row = await consumeQueueJobSse(eventsUrl, auth, signal, onUpdate);
    onUpdate(row);
  } catch (e) {
    if (signal.aborted || isAbortError(e)) {
      return;
    }
    // Dashboard still polls via refreshDashboard when SSE is unavailable.
  }
}

export async function pollQueueJobUntilTerminal(
  queueId: string,
  auth: Record<string, string>,
  signal: AbortSignal,
  onProgress?: (row: QueueJobRow) => void,
  onGatewayBlip?: () => void,
): Promise<QueueJobRow> {
  const deadline = Date.now() + STUDIO_QUEUE_MAX_WAIT_MS;
  let lastStatus = "unknown";
  let gatewayBlips = 0;
  while (Date.now() < deadline) {
    if (signal.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    let pr: Response;
    try {
      pr = await fetchWithTransientRetry(
        `${STUDIO_API_BASE}/api/studio/queue/jobs/${encodeURIComponent(queueId)}`,
        { headers: auth, signal },
        8,
      );
    } catch (e) {
      if (signal.aborted || isAbortError(e)) {
        throw e;
      }
      gatewayBlips++;
      onGatewayBlip?.();
      await delay(Math.min(STUDIO_QUEUE_POLL_MS * 2, 8000), signal);
      continue;
    }
    if (RETRYABLE_HTTP.has(pr.status)) {
      gatewayBlips++;
      onGatewayBlip?.();
      await delay(Math.min(STUDIO_QUEUE_POLL_MS * 2, 8000), signal);
      continue;
    }
    let row: QueueJobRow & { detail?: unknown };
    try {
      row = await readApiJson<QueueJobRow & { detail?: unknown }>(pr);
    } catch {
      gatewayBlips++;
      onGatewayBlip?.();
      await delay(STUDIO_QUEUE_POLL_MS, signal);
      continue;
    }
    if (signal.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    if (!pr.ok) {
      if (RETRYABLE_HTTP.has(pr.status)) {
        gatewayBlips++;
        onGatewayBlip?.();
        await delay(STUDIO_QUEUE_POLL_MS * 2, signal);
        continue;
      }
      throw new Error(formatApiDetail(row.detail));
    }
    gatewayBlips = 0;
    lastStatus = row.status;
    if (row.status === "completed") {
      return row;
    }
    if (row.status === "dead") {
      throw new Error(row.last_error?.trim() || "Job failed (dead letter)");
    }
    if (onProgress && (row.status === "running" || row.status === "pending")) {
      onProgress(row);
    }
    await delay(STUDIO_QUEUE_POLL_MS, signal);
  }
  throw new Error(
    `Timed out after ${STUDIO_QUEUE_MAX_WAIT_MS / 60000} minutes waiting for job ${queueId} (last status: ${lastStatus}${gatewayBlips > 0 ? `; ${gatewayBlips} gateway blips` : ""})`,
  );
}

export type WaitForQueueJobOptions = {
  onProgress?: (row: QueueJobRow) => void;
  onGatewayBlip?: () => void;
  onTransportMode?: (mode: QueueTransportMode) => void;
};

/** Try queue SSE first (with one reconnect); fall back to 2s GET polling if the edge or browser drops the stream. */
export async function waitForQueueJobCompletion(
  queueId: string,
  auth: Record<string, string>,
  signal: AbortSignal,
  options: WaitForQueueJobOptions = {},
): Promise<QueueJobRow> {
  const { onProgress, onGatewayBlip, onTransportMode } = options;
  const eventsUrl = `${STUDIO_API_BASE}/api/studio/queue/jobs/${encodeURIComponent(queueId)}/events`;

  for (let attempt = 0; attempt < SSE_RECONNECT_ATTEMPTS; attempt++) {
    try {
      onTransportMode?.("sse");
      return await consumeQueueJobSse(eventsUrl, auth, signal, onProgress);
    } catch (e) {
      if (signal.aborted || isAbortError(e)) {
        throw e;
      }
      const msg = e instanceof Error ? e.message : "";
      const shouldPoll =
        e instanceof SseTransportError ||
        msg.includes("queue SSE max duration exceeded") ||
        isGatewayDetailMessage(msg);
      if (!shouldPoll) {
        throw e;
      }
      if (attempt + 1 < SSE_RECONNECT_ATTEMPTS && e instanceof SseTransportError) {
        await delay(800 * (attempt + 1), signal);
        continue;
      }
      onTransportMode?.("polling");
      return await pollQueueJobUntilTerminal(queueId, auth, signal, onProgress, onGatewayBlip);
    }
  }

  onTransportMode?.("polling");
  return await pollQueueJobUntilTerminal(queueId, auth, signal, onProgress, onGatewayBlip);
}
