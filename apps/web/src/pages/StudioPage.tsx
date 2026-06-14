import type {
  StudioBillingStatus,
  StudioComfyStatusPayload,
  StudioDashboardPayload,
  StudioJobSummary,
  StudioQueueJobSummary,
  StudioQueueSloSnapshot,
  StudioUsageInfo,
  StudioWorkerHints,
} from "@immersive/studio-types";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { EngravedBackdrop } from "../components/EngravedBackdrop";
import { STUDIO_API_BASE, STUDIO_API_READY, studioWorkerDisplayOrigin } from "../studioApiConfig";
import "../App.css";
import "./StudioPage.css";

const API_KEY_STORAGE = "immersive_studio_api_key";
const ENGINE_TARGET_STORAGE = "immersive_studio_engine_target";
const PROMPT_STORAGE = "immersive_studio_prompt";
const LAST_JOB_STORAGE = "immersive_studio_last_job_v1";
const ACTIVE_QUEUE_STORAGE = "immersive_studio_active_queue_id";
const JOB_OPTS_STORAGE = "immersive_studio_job_opts_v1";

type PersistedJobResult = {
  job_id: string;
  zip_path: string;
  errors: string[];
  texture_logs: string[];
  mesh_logs: string[];
  prompt?: string;
};

function readStoredPrompt(): string {
  try {
    return localStorage.getItem(PROMPT_STORAGE) ?? "";
  } catch {
    return "";
  }
}

function readStoredJobResult(): PersistedJobResult | null {
  try {
    const raw = localStorage.getItem(LAST_JOB_STORAGE);
    if (!raw) {
      return null;
    }
    const j = JSON.parse(raw) as PersistedJobResult;
    if (!j?.job_id) {
      return null;
    }
    return j;
  } catch {
    return null;
  }
}

function readStoredJobOpts(): { generateTextures: boolean; exportMesh: boolean } {
  try {
    const raw = localStorage.getItem(JOB_OPTS_STORAGE);
    if (!raw) {
      return { generateTextures: false, exportMesh: false };
    }
    const j = JSON.parse(raw) as { generateTextures?: boolean; exportMesh?: boolean };
    return {
      generateTextures: Boolean(j.generateTextures),
      exportMesh: Boolean(j.exportMesh),
    };
  } catch {
    return { generateTextures: false, exportMesh: false };
  }
}

function isGatewayDetailMessage(msg: string): boolean {
  return (
    /Gateway or tunnel returned HTTP/i.test(msg) ||
    /gateway_status/i.test(msg) ||
    /invalid JSON.*502/i.test(msg)
  );
}

type StudioCategory = "prop" | "environment_piece" | "character_base" | "material_library";
type StudioStyle = "realistic_hd_pbr" | "anime_stylized" | "toon_bold";
type StudioEngineTarget = "unity" | "unreal";

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

/** Human-readable age for queue SLO fields (worker returns seconds as float). */
function formatQueueAgeSeconds(seconds: number | null | undefined): string | null {
  if (seconds == null || Number.isNaN(seconds)) {
    return null;
  }
  const s = Math.max(0, seconds);
  if (s < 120) {
    return `${Math.round(s)}s`;
  }
  const m = s / 60;
  if (m < 120) {
    return `${Math.round(m)}m`;
  }
  return `${(m / 60).toFixed(1)}h`;
}

/** Mesh step fell back from Tripo to free Blender placeholder (e.g. empty API credits). */
function meshLogsIndicateTripoFallback(logs: readonly string[]): boolean {
  return logs.some(
    (line) =>
      /tripo mesh unavailable/i.test(line) ||
      /placeholder mesh instead/i.test(line) ||
      /top up api credits/i.test(line),
  );
}

/** Ages above this (seconds) usually indicate the queue is not draining, not normal backlog. */
const STALE_QUEUE_AGE_SECONDS = 3600;

type RecentJobDisplay = StudioJobSummary & { queue_id?: string };

function queuePromptSummary(payload: StudioQueueJobSummary["payload"]): string {
  const p = typeof payload?.user_prompt === "string" ? payload.user_prompt.trim() : "";
  if (!p) {
    return "(queue job)";
  }
  return p.length > 120 ? `${p.slice(0, 120)}…` : p;
}

/** In-flight queue rows first, then persisted index jobs (deduped by studio_job_id). */
function mergeRecentJobRows(
  indexJobs: StudioJobSummary[],
  queueJobs: StudioQueueJobSummary[] | undefined,
): RecentJobDisplay[] {
  const indexedIds = new Set(indexJobs.map((j) => j.job_id));
  const queueRows: RecentJobDisplay[] = [];
  for (const q of queueJobs ?? []) {
    if (q.studio_job_id && indexedIds.has(q.studio_job_id)) {
      continue;
    }
    if (q.status !== "pending" && q.status !== "running" && q.status !== "dead") {
      continue;
    }
    queueRows.push({
      job_id: q.studio_job_id || q.id,
      folder: "",
      created_at: q.created_at,
      status: q.status === "pending" ? "queued" : q.status,
      summary: queuePromptSummary(q.payload),
      has_textures: Boolean(q.payload?.generate_textures),
      error: q.last_error ?? null,
      queue_id: q.id,
    });
  }
  return [...queueRows, ...indexJobs];
}

function queueSloLooksStale(q: StudioQueueSloSnapshot): boolean {
  const p = q.pending_oldest_age_seconds;
  const r = q.running_oldest_age_seconds;
  return (
    (typeof p === "number" && p >= STALE_QUEUE_AGE_SECONDS) ||
    (typeof r === "number" && r >= STALE_QUEUE_AGE_SECONDS)
  );
}

function StudioQueueSloLine({ q }: { q: StudioQueueSloSnapshot }) {
  const po = formatQueueAgeSeconds(q.pending_oldest_age_seconds);
  const ro = formatQueueAgeSeconds(q.running_oldest_age_seconds);
  const stale = queueSloLooksStale(q);
  return (
    <>
      <p className="studio-queue-slo">
        Queue snapshot: <strong>{q.pending_claimable_count}</strong> claimable pending
        {po ? <> (oldest ~{po})</> : null}, <strong>{q.running_count}</strong> running
        {ro ? <> (longest ~{ro})</> : null}.
      </p>
      {stale ? (
        <p className="studio-queue-slo-warn" role="status">
          Very old ages usually mean work is not finishing: confirm the API process and queue consumer are running (
          <code>STUDIO_EMBEDDED_QUEUE_WORKER</code>), check tunnel and VM health, and ensure Ollama/Comfy steps are not
          blocked if those features are enabled. Stuck rows are auto-marked <strong>dead</strong> after{" "}
          <code>STUDIO_QUEUE_MAX_JOB_AGE_S</code> (default 4h) — raise it for large texture batches.
        </p>
      ) : null}
    </>
  );
}

function comfyFailureLooksLikeTimeout(detail: string | null | undefined): boolean {
  const d = (detail ?? "").toLowerCase();
  return d.includes("timed out") || /\btimeout\b/.test(d);
}

/** Comfy reachability line — avoid calling a slow tunnel failure &quot;not running&quot;. */
function comfyReachabilityLabel(reachable: boolean, detail: string | null): string {
  if (reachable) {
    return "reachable";
  }
  return comfyFailureLooksLikeTimeout(detail) ? "probe timed out" : "not running";
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

/** Matches worker default `STUDIO_COMFY_URL` when unset; used only for display when the API body is not a full Comfy payload. */
const DEFAULT_COMFY_DISPLAY_URL = "https://comfy.immersivelabs.space";

/**
 * `readApiJson` succeeds on edge-coerced gateway errors (`gateway_status`, `detail`) which are not
 * `StudioComfyStatusPayload` — missing `url` made the UI claim "Studio API request failed".
 */
function parseComfyStatusResponse(r: Response, text: string): StudioComfyStatusPayload {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    const t = text.trim();
    const snippet = t.slice(0, 160).replace(/\s+/g, " ");
    const html =
      t.startsWith("<!") || t.toLowerCase().startsWith("<html")
        ? " Response was HTML (gateway 502/504 or timeout), not JSON."
        : "";
    return {
      reachable: false,
      url: DEFAULT_COMFY_DISPLAY_URL,
      detail: `HTTP ${r.status}: invalid JSON.${html}${snippet ? ` Body: ${snippet}` : ""}`,
    };
  }

  if (raw !== null && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    if (typeof o.gateway_status === "number") {
      const base =
        typeof o.detail === "string" ? o.detail : "Gateway returned an error instead of Comfy JSON.";
      const host = typeof o.origin_host === "string" ? ` (origin: ${o.origin_host})` : "";
      return {
        reachable: false,
        url: DEFAULT_COMFY_DISPLAY_URL,
        detail: `${base}${host}`,
      };
    }
    if (
      typeof o.reachable === "boolean" &&
      typeof o.url === "string" &&
      (o.detail === null || o.detail === undefined || typeof o.detail === "string")
    ) {
      return {
        reachable: o.reachable,
        url: o.url,
        detail: typeof o.detail === "string" ? o.detail : null,
      };
    }
    const d = o.detail;
    let detailStr: string;
    if (typeof d === "string") {
      detailStr = d;
    } else if (Array.isArray(d)) {
      detailStr = JSON.stringify(d);
    } else if (d !== null && d !== undefined && typeof d === "object") {
      detailStr = JSON.stringify(d);
    } else {
      detailStr = "Unexpected /api/studio/comfy-status JSON shape.";
    }
    return {
      reachable: false,
      url: DEFAULT_COMFY_DISPLAY_URL,
      detail: detailStr,
    };
  }

  return {
    reachable: false,
    url: DEFAULT_COMFY_DISPLAY_URL,
    detail: "Unexpected /api/studio/comfy-status response (not a JSON object).",
  };
}

const STUDIO_QUEUE_POLL_MS = 2000;
/** Must cover long Comfy + LLM runs after SSE closes (see STUDIO_QUEUE_SSE_MAX_DURATION_S on the worker). */
const STUDIO_QUEUE_MAX_WAIT_MS = 120 * 60 * 1000;

class SseTransportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SseTransportError";
  }
}

/**
 * ``GET …/queue/jobs/{id}/events`` (``text/event-stream``) with ``Authorization`` — EventSource cannot set headers.
 * Throws {@link SseTransportError} for proxy/stream issues so the caller can fall back to GET polling.
 */
async function consumeQueueJobSse(
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

async function pollQueueJobUntilTerminal(
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

/** Try queue SSE first; fall back to 2s GET polling if the edge or browser does not keep the stream open. */
async function waitForQueueJobCompletion(
  queueId: string,
  auth: Record<string, string>,
  signal: AbortSignal,
  onProgress?: (row: QueueJobRow) => void,
  onGatewayBlip?: () => void,
): Promise<QueueJobRow> {
  const eventsUrl = `${STUDIO_API_BASE}/api/studio/queue/jobs/${encodeURIComponent(queueId)}/events`;
  try {
    return await consumeQueueJobSse(eventsUrl, auth, signal, onProgress);
  } catch (e) {
    if (signal.aborted || isAbortError(e)) {
      throw e;
    }
    if (e instanceof SseTransportError) {
      return await pollQueueJobUntilTerminal(queueId, auth, signal, onProgress, onGatewayBlip);
    }
    const msg = e instanceof Error ? e.message : "";
    if (msg.includes("queue SSE max duration exceeded") || isGatewayDetailMessage(msg)) {
      return await pollQueueJobUntilTerminal(queueId, auth, signal, onProgress, onGatewayBlip);
    }
    throw e;
  }
}

/** Tunnel / origin often returns transient 5xx when the VM is busy (e.g. Ollama + Comfy). */
const RETRYABLE_HTTP = new Set([502, 503, 504, 524, 530]);

function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

function delay(ms: number, signal?: AbortSignal | null): Promise<void> {
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

async function fetchWithTransientRetry(
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

type QueueJobRow = {
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

export function StudioPage() {
  const storedJobOpts = readStoredJobOpts();
  const [prompt, setPrompt] = useState(() => {
    const stored = readStoredPrompt();
    if (stored.trim()) {
      return stored;
    }
    return readStoredJobResult()?.prompt ?? "";
  });
  const [category, setCategory] = useState<StudioCategory>("prop");
  const [stylePreset, setStylePreset] = useState<StudioStyle>("toon_bold");
  const [mock, setMock] = useState(false);
  const [generateTextures, setGenerateTextures] = useState(storedJobOpts.generateTextures);
  const [exportMesh, setExportMesh] = useState(storedJobOpts.exportMesh);
  const [engineTarget, setEngineTarget] = useState<StudioEngineTarget>("unity");
  const [loading, setLoading] = useState(false);
  const [packLoading, setPackLoading] = useState(false);
  const [jobLoading, setJobLoading] = useState(false);
  /** Long job: Comfy / mesh sub-step from queue ``progress`` field (SSE or poll). */
  const [jobRunProgress, setJobRunProgress] = useState<string | null>(null);
  /** Transient tunnel blip while polling — job may still be running on the server. */
  const [jobGatewayNotice, setJobGatewayNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [spec, setSpec] = useState<Record<string, unknown> | null>(null);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [packResult, setPackResult] = useState<{ output_dir: string; job_id: string } | null>(null);
  const [jobResult, setJobResult] = useState<PersistedJobResult | null>(() => readStoredJobResult());
  const [health, setHealth] = useState<"checking" | "ok" | "error">("checking");
  /** From GET /api/studio/health when present (helps confirm prod worker redeploy). */
  const [workerVersion, setWorkerVersion] = useState<string | null>(null);
  /** Extra context when health check fails (e.g. Cloudflare 530 tunnel). */
  const [healthErrorHint, setHealthErrorHint] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [usage, setUsage] = useState<StudioUsageInfo | null>(null);
  const [billing, setBilling] = useState<StudioBillingStatus | null>(null);
  const [comfy, setComfy] = useState<StudioComfyStatusPayload | null>(null);
  const [jobs, setJobs] = useState<StudioJobSummary[]>([]);
  const [queueJobs, setQueueJobs] = useState<StudioQueueJobSummary[]>([]);
  const [jobsRoot, setJobsRoot] = useState<string | null>(null);
  const [workerHints, setWorkerHints] = useState<StudioWorkerHints | null>(null);
  const [queueSlo, setQueueSlo] = useState<StudioQueueSloSnapshot | null>(null);
  /** When true, slow down dashboard polling (tab in background). */
  const [dashboardPollSlow, setDashboardPollSlow] = useState(false);
  /** Aborts in-flight queue polling when leaving /studio or starting a new run. */
  const jobPollAbortRef = useRef<AbortController | null>(null);
  const jobLoadingRef = useRef(false);
  const resumeQueueRef = useRef(false);

  useEffect(() => {
    jobLoadingRef.current = jobLoading;
  }, [jobLoading]);

  useEffect(() => {
    try {
      localStorage.setItem(PROMPT_STORAGE, prompt);
    } catch {
      /* ignore */
    }
  }, [prompt]);

  useEffect(() => {
    try {
      localStorage.setItem(
        JOB_OPTS_STORAGE,
        JSON.stringify({ generateTextures, exportMesh }),
      );
    } catch {
      /* ignore */
    }
  }, [generateTextures, exportMesh]);

  useEffect(() => {
    if (!jobResult) {
      return;
    }
    try {
      localStorage.setItem(LAST_JOB_STORAGE, JSON.stringify(jobResult));
    } catch {
      /* ignore */
    }
  }, [jobResult]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(API_KEY_STORAGE);
      if (stored) {
        setApiKey(stored);
      }
      const storedEngine = window.localStorage.getItem(ENGINE_TARGET_STORAGE);
      if (storedEngine === "unity" || storedEngine === "unreal") {
        setEngineTarget(storedEngine);
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

  const checkHealth = useCallback((signal?: AbortSignal) => {
    if (!STUDIO_API_READY) {
      setHealth("error");
      setHealthErrorHint(null);
      return;
    }
    setHealth("checking");
    setHealthErrorHint(null);
    setWorkerVersion(null);
    void fetchWithTransientRetry(`${STUDIO_API_BASE}/api/studio/health`, { signal }, 5)
      .then(async (r) => {
        if (signal?.aborted) {
          return;
        }
        if (!r.ok) {
          if (jobLoadingRef.current && RETRYABLE_HTTP.has(r.status)) {
            setHealth("ok");
            setHealthErrorHint(
              "Brief gateway timeout while a full job is running on the VM (textures/mesh can block the API). Polling continues — refresh if this persists.",
            );
            return;
          }
          setHealth("error");
          setWorkerVersion(null);
          if (r.status === 530) {
            setHealthErrorHint(
              "Cloudflare HTTP 530 — the tunnel has no active connector (cloudflared not running on the GCE VM). " +
                "Fix: GCP Console → Compute → immersive-studio-worker → SSH in browser → run " +
                "sudo bash scripts/studio-cloudflare-tunnel/vm-recover-tunnel-and-docker.sh from /opt/immersive.labs. " +
                "Or paste the script from the repo. Comfy at comfy.immersivelabs.space uses the same tunnel. " +
                "See scripts/studio-cloudflare-tunnel/README.md.",
            );
          } else if (r.status >= 500) {
            setHealthErrorHint(
              `Gateway or server error (HTTP ${r.status}). On the free-tier VM this is often a brief origin timeout while Comfy or a job holds the CPU — wait and click Refresh, or check cloudflared/docker on the VM.`,
            );
          } else {
            setHealthErrorHint(`Unexpected HTTP ${r.status} from ${STUDIO_API_BASE}/api/studio/health.`);
          }
          return;
        }
        try {
          const j = await readApiJson<{ auth_required?: boolean; worker_version?: string }>(r);
          if (signal?.aborted) {
            return;
          }
          setHealth("ok");
          setHealthErrorHint(null);
          setAuthRequired(Boolean(j?.auth_required));
          setWorkerVersion(typeof j?.worker_version === "string" ? j.worker_version : null);
        } catch {
          if (signal?.aborted) {
            return;
          }
          setHealth("error");
          setWorkerVersion(null);
          setHealthErrorHint(
            "The URL responded, but the body was not JSON (often an error page in front of the API). Fix DNS / tunnel / Worker upstream so /api/studio/health returns the worker JSON.",
          );
        }
      })
      .catch((e) => {
        if (signal?.aborted || isAbortError(e)) {
          return;
        }
        setHealth("error");
        setWorkerVersion(null);
        setHealthErrorHint("Network error — the browser could not complete a request to the Studio API (offline, CORS, or blocked).");
      });
  }, []);

  /** One GET bundles usage + billing + jobs (fewer tunnel round-trips when the VM is busy). */
  const refreshDashboard = useCallback((signal?: AbortSignal) => {
    if (!STUDIO_API_READY) {
      setJobs([]);
      setQueueJobs([]);
      setUsage(null);
      setBilling(null);
      setWorkerHints(null);
      setQueueSlo(null);
      return;
    }
    void fetchWithTransientRetry(`${STUDIO_API_BASE}/api/studio/dashboard`, {
      headers: authHeaders(),
      signal,
    })
      .then(async (r) => {
        if (signal?.aborted) {
          return null;
        }
        if (!r.ok) {
          return null;
        }
        try {
          return await readApiJson<StudioDashboardPayload>(r);
        } catch {
          return null;
        }
      })
      .then((d) => {
        if (signal?.aborted || !d) {
          return;
        }
        setUsage(d.usage);
        setBilling(d.billing);
        setJobs(d.jobs?.jobs ?? []);
        setQueueJobs(d.queue_jobs?.jobs ?? []);
        if (d.jobs?.jobs_root) {
          setJobsRoot(d.jobs.jobs_root);
        }
        setWorkerHints(d.worker_hints ?? null);
        setQueueSlo(d.queue_slo ?? null);
      })
      .catch((e) => {
        if (signal?.aborted || isAbortError(e)) {
          return;
        }
        setJobs([]);
        setQueueJobs([]);
        setUsage(null);
        setBilling(null);
        setWorkerHints(null);
        setQueueSlo(null);
      });
  }, [authHeaders]);

  const finishJobFromQueueRow = useCallback(
    (row: QueueJobRow, promptHint: string) => {
      if (row.status !== "completed") {
        throw new Error(`Unexpected terminal queue status: ${row.status}`);
      }
      const data = row.result;
      if (!data) {
        throw new Error("Job completed without result payload");
      }
      setSpec(data.spec ?? null);
      const next: PersistedJobResult = {
        job_id: data.job_id ?? "?",
        zip_path: data.zip_path ?? "",
        errors: data.errors ?? [],
        texture_logs: data.texture_logs ?? [],
        mesh_logs: data.mesh_logs ?? [],
        prompt: promptHint,
      };
      setJobResult(next);
      setJobGatewayNotice(null);
      setError(null);
      try {
        localStorage.removeItem(ACTIVE_QUEUE_STORAGE);
      } catch {
        /* ignore */
      }
      void refreshDashboard();
    },
    [refreshDashboard],
  );

  const followQueueJob = useCallback(
    async (queueId: string, promptHint: string, signal: AbortSignal) => {
      const row = await waitForQueueJobCompletion(
        queueId,
        authHeaders(),
        signal,
        (r) => {
          const p = r.progress;
          if (p && typeof p.done === "number" && typeof p.total === "number" && p.total > 0) {
            const w = p.width && p.height ? ` · ${p.width}×${p.height}` : "";
            setJobRunProgress(
              `Textures ${p.done}/${p.total}${p.label ? ` · ${p.label}` : ""}${w}`,
            );
          } else if (r.status === "running" || r.status === "pending") {
            setJobRunProgress(`Job ${r.status} on server…`);
          } else {
            setJobRunProgress(null);
          }
        },
        () => {
          setJobGatewayNotice(
            "Tunnel returned a brief HTTP 502/504 while checking job status — the job may still be running on the VM. Waiting…",
          );
        },
      );
      finishJobFromQueueRow(row, promptHint);
    },
    [authHeaders, finishJobFromQueueRow],
  );

  const recentJobs = mergeRecentJobRows(jobs, queueJobs);

  const refreshComfy = useCallback((signal?: AbortSignal) => {
    if (!STUDIO_API_READY) {
      setComfy(null);
      return;
    }
    void fetchWithTransientRetry(`${STUDIO_API_BASE}/api/studio/comfy-status`, { signal })
      .then(async (r) => {
        if (signal?.aborted) {
          return null;
        }
        const text = await r.text();
        if (signal?.aborted) {
          return null;
        }
        return parseComfyStatusResponse(r, text);
      })
      .then((v) => {
        if (signal?.aborted || v == null) {
          return;
        }
        setComfy(v);
      })
      .catch((e) => {
        if (signal?.aborted || isAbortError(e)) {
          return;
        }
        setComfy({
          reachable: false,
          url: DEFAULT_COMFY_DISPLAY_URL,
          detail: e instanceof Error ? e.message : "Network request failed",
        });
      });
  }, []);

  useEffect(() => {
    if (!STUDIO_API_READY) {
      setHealth("error");
      return;
    }
    const ac = new AbortController();
    checkHealth(ac.signal);
    refreshComfy(ac.signal);
    return () => ac.abort();
  }, [checkHealth, refreshComfy]);

  useEffect(() => {
    const onVis = () => setDashboardPollSlow(document.visibilityState === "hidden");
    onVis();
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => {
    if (!STUDIO_API_READY) {
      return;
    }
    const ac = new AbortController();
    void refreshDashboard(ac.signal);
    // Full jobs saturate a small VM; background tabs poll less to ease tunnel + origin load.
    const pollMs = jobLoading ? 30_000 : dashboardPollSlow ? 90_000 : 5000;
    const t = window.setInterval(() => void refreshDashboard(ac.signal), pollMs);
    return () => {
      ac.abort();
      window.clearInterval(t);
    };
  }, [refreshDashboard, jobLoading, dashboardPollSlow]);

  useEffect(() => {
    if (!STUDIO_API_READY || resumeQueueRef.current) {
      return;
    }
    let queueId: string | null = null;
    try {
      queueId = localStorage.getItem(ACTIVE_QUEUE_STORAGE);
    } catch {
      queueId = null;
    }
    if (!queueId?.trim()) {
      return;
    }
    resumeQueueRef.current = true;
    setJobLoading(true);
    setJobGatewayNotice("Resuming in-flight job after page reload…");
    setError(null);
    jobPollAbortRef.current?.abort();
    const runAc = new AbortController();
    jobPollAbortRef.current = runAc;
    const promptHint = readStoredPrompt() || readStoredJobResult()?.prompt || "";
    void followQueueJob(queueId, promptHint, runAc.signal)
      .catch((err) => {
        if (runAc.signal.aborted || isAbortError(err)) {
          return;
        }
        const msg = err instanceof Error ? err.message : String(err);
        if (!isGatewayDetailMessage(msg)) {
          setError(`${msg} — worker: ${studioWorkerDisplayOrigin()}`);
        } else {
          setJobGatewayNotice(
            "Could not reach the queue API after reload — check Recent jobs below or run Refresh now.",
          );
        }
      })
      .finally(() => {
        if (jobPollAbortRef.current === runAc) {
          jobPollAbortRef.current = null;
        }
        setJobRunProgress(null);
        setJobLoading(false);
      });
  }, [STUDIO_API_READY, followQueueJob]);

  useEffect(
    () => () => {
      jobPollAbortRef.current?.abort();
    },
    [],
  );

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
      const msg = err instanceof Error ? err.message : String(err);
      // Makes it obvious when `.env` points the browser at a remote worker (stale deploy) vs local 8787.
      setError(`${msg} — worker: ${studioWorkerDisplayOrigin()}`);
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
        body: JSON.stringify({ spec, output_name: outputName, engine_target: engineTarget }),
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
    setJobRunProgress(null);
    setJobGatewayNotice(null);
    setPackResult(null);
    jobPollAbortRef.current?.abort();
    const runAc = new AbortController();
    jobPollAbortRef.current = runAc;
    const signal = runAc.signal;
    try {
      const idem =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `web-${Date.now()}`;
      const enqRes = await fetch(`${STUDIO_API_BASE}/api/studio/queue/jobs`, {
        method: "POST",
        signal,
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          prompt,
          category,
          style_preset: stylePreset,
          mock,
          generate_textures: generateTextures,
          export_mesh: exportMesh,
          engine_target: engineTarget,
          unity_urp_hint: "6000.0.x LTS (pin when smoke-tested)",
          max_attempts: 1,
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
      try {
        localStorage.setItem(ACTIVE_QUEUE_STORAGE, queueId);
      } catch {
        /* ignore */
      }

      await followQueueJob(queueId, prompt, signal);
      if (signal.aborted) {
        return;
      }
      setJobRunProgress(null);
    } catch (err) {
      if (signal.aborted || isAbortError(err)) {
        return;
      }
      const msg = err instanceof Error ? err.message : String(err);
      if (isGatewayDetailMessage(msg)) {
        setJobGatewayNotice(
          "Lost contact with the queue API, but the job may still be running — check Recent jobs or refresh the page to resume polling.",
        );
      } else {
        setError(`${msg} — worker: ${studioWorkerDisplayOrigin()}`);
        try {
          localStorage.removeItem(ACTIVE_QUEUE_STORAGE);
        } catch {
          /* ignore */
        }
      }
    } finally {
      if (jobPollAbortRef.current === runAc) {
        jobPollAbortRef.current = null;
      }
      setJobRunProgress(null);
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
            index), optionally invoke <strong>ComfyUI</strong> for albedo textures, then import in <strong>Unity</strong>{" "}
            (<code>packages/studio-unity</code>) or <strong>Unreal Engine 5</strong> (
            <code>packages/studio-unreal</code>) using the import-target toggle below. Start with the on-site{" "}
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
                <strong>Cloudflare Pages:</strong> Project → Settings → Environment variables → add{" "}
                <code>VITE_STUDIO_API_URL</code> = <code>https://your-worker.example.com</code> → trigger a new build.
                <br />
                <strong>Local dev:</strong> run <code>npm run dev</code> (defaults to{" "}
                <code>http://127.0.0.1:8787</code>) or put the same value in{" "}
                <code>apps/web/.env.development.local</code>.
              </span>
            </div>
          ) : (
            <div className={`studio-health studio-health--${health}`} role="status">
              {health === "checking" && "Checking worker…"}
              {health === "ok" && (
                <>
                  Worker{workerVersion ? ` v${workerVersion}` : ""} reachable at {studioWorkerDisplayOrigin()}
                </>
              )}
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
                  <button type="button" className="studio-retry" onClick={() => checkHealth()}>
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
                onClick={() => void refreshDashboard()}
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
              : {comfyReachabilityLabel(comfy.reachable, comfy.detail)}
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
                  ) : comfyFailureLooksLikeTimeout(comfy.detail) ? (
                    <>
                      <strong>HTTP probe timed out.</strong> Comfy may be down, overloaded, or the path to it (tunnel,
                      network) too slow. On the worker VM raise <code>STUDIO_COMFY_PROBE_TIMEOUT_S</code>, verify Comfy is
                      listening and <code>cloudflared</code> is healthy, then click Refresh.
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
              <button type="button" className="studio-retry" onClick={() => void refreshComfy()}>
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

            <label className="studio-label">
              Import target (pack.zip)
              <select
                className="studio-input"
                value={engineTarget}
                onChange={(e) => {
                  const next = e.target.value as StudioEngineTarget;
                  setEngineTarget(next);
                  try {
                    window.localStorage.setItem(ENGINE_TARGET_STORAGE, next);
                  } catch {
                    /* ignore */
                  }
                }}
              >
                <option value="unity">Unity (URP) — UnityImportNotes.md</option>
                <option value="unreal">Unreal Engine 5 — UnrealImportNotes.md</option>
              </select>
            </label>

            <label className="studio-check">
              <input type="checkbox" checked={mock} onChange={(e) => setMock(e.target.checked)} />
              Mock mode (no Ollama — deterministic spec for wiring)
            </label>
            {!mock && workerHints ? (
              <p className="studio-ollama-hint">
                Full jobs call Ollama at <code>{workerHints.ollama_base_url}</code> (model{" "}
                <code>{workerHints.ollama_model}</code>, read timeout{" "}
                <code>{Math.round(workerHints.ollama_read_timeout_s)}s</code>
                {workerHints.ollama_num_predict != null ? (
                  <>
                    , output cap <code>{workerHints.ollama_num_predict}</code> tokens (
                    <code>STUDIO_OLLAMA_NUM_PREDICT</code>)
                  </>
                ) : null}
                ). Streaming is on by default unless <code>STUDIO_OLLAMA_STREAM=0</code>. The worker preflights Ollama
                (<code>GET /api/tags</code>) before each LLM call by default (fail fast). For quick UI checks, use mock
                mode; on the server set <code>STUDIO_OLLAMA_DISABLED=1</code> for mock-only hosts; otherwise tune{" "}
                <code>STUDIO_OLLAMA_READ_TIMEOUT_S</code>, <code>STUDIO_OLLAMA_CONNECT_TIMEOUT_S</code>, add RAM/swap, or
                use a smaller <code>STUDIO_OLLAMA_MODEL</code> if specs time out.
              </p>
            ) : null}

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
            {jobLoading && jobRunProgress ? (
              <p className="studio-job-run-progress" role="status" aria-live="polite">
                {jobRunProgress}
              </p>
            ) : null}
            {jobGatewayNotice ? (
              <p className="studio-job-gateway-notice" role="status" aria-live="polite">
                {jobGatewayNotice}
              </p>
            ) : null}
          </form>

          {error ? <pre className="studio-error studio-error--prominent">{error}</pre> : null}

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
              {meshLogsIndicateTripoFallback(jobResult.mesh_logs) ? (
                <p className="studio-job-warn" role="status">
                  <strong>Tripo credits unavailable.</strong> This pack used the free Blender placeholder mesh instead
                  of prompt-faithful 3D. Top up at{" "}
                  <a href="https://platform.tripo3d.ai" target="_blank" rel="noreferrer">
                    platform.tripo3d.ai
                  </a>{" "}
                  (OpenAPI credits are separate from Tripo Studio web credits).
                </p>
              ) : null}
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
              <div className="studio-job-result-actions">
                <button
                  type="button"
                  className="btn btn-primary studio-download"
                  disabled={!STUDIO_API_READY}
                  onClick={() => void downloadJobZip(jobResult.job_id)}
                >
                  Download pack.zip
                </button>
                {billing?.stripe_customer_linked ? (
                  <button type="button" className="btn btn-ghost" onClick={() => void openStripePortal()}>
                    Open Stripe billing
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}

          {workerHints && STUDIO_API_READY ? (
            <section className="studio-worker-hints" aria-label="Worker LLM and queue settings">
              <h2 className="studio-worker-hints-title">Worker LLM and queue</h2>
              <p className="studio-worker-hints-body">
                Ollama read timeout: <code>{Math.round(workerHints.ollama_read_timeout_s)}s</code> (
                <code>STUDIO_OLLAMA_READ_TIMEOUT_S</code>, max{" "}
                <code>{Math.round(workerHints.ollama_read_timeout_max_s ?? 3600)}</code>
                {workerHints.ollama_connect_timeout_s != null ? (
                  <>
                    ; connect <code>{Math.round(workerHints.ollama_connect_timeout_s)}s</code> (
                    <code>STUDIO_OLLAMA_CONNECT_TIMEOUT_S</code>)
                  </>
                ) : null}
                {workerHints.ollama_preflight === false ? (
                  <>
                    ; preflight <strong>off</strong>
                  </>
                ) : null}
                {workerHints.ollama_disabled ? (
                  <>
                    ; <strong>Ollama disabled</strong> (<code>STUDIO_OLLAMA_DISABLED</code> — mock specs only)
                  </>
                ) : null}
                ). Output token cap:{" "}
                <code>{workerHints.ollama_num_predict ?? "—"}</code> (<code>STUDIO_OLLAMA_NUM_PREDICT</code>). Model{" "}
                <code>{workerHints.ollama_model}</code> (<code>STUDIO_OLLAMA_MODEL</code>) at{" "}
                <code>{workerHints.ollama_base_url}</code> (<code>STUDIO_OLLAMA_URL</code>). ComfyUI per-image wait:{" "}
                <code>{Math.round(workerHints.comfy_image_wait_s ?? 420)}s</code> (<code>STUDIO_COMFY_IMAGE_WAIT_S</code>
                ); parallel texture calls: <code>{workerHints.comfy_max_concurrent ?? 1}</code> (
                <code>STUDIO_COMFY_MAX_CONCURRENT</code>
                ). Texture size cap: <code>{workerHints.texture_global_max_side ?? "—"}</code>px (
                <code>STUDIO_TEXTURE_MAX_SIDE</code>
                ). Queue backend: <code>{workerHints.queue_backend ?? "sqlite"}</code>
                {workerHints.queue_max_job_age_s != null ? (
                  <>
                    . Auto-cancel pending/running queue rows after{" "}
                    <code>{Math.round(workerHints.queue_max_job_age_s / 3600)}h</code> (
                    <code>STUDIO_QUEUE_MAX_JOB_AGE_S</code>)
                  </>
                ) : null}
                {workerHints.postgres_configured ? " (Postgres URL set)" : ""}
                {workerHints.redis_configured ? " (Redis URL set)" : ""}
                {workerHints.mesh_provider ? (
                  <>
                    . Mesh: <code>{workerHints.mesh_provider}</code>
                    {workerHints.mesh_tripo_fallback_to_blender ? (
                      <> — tries Tripo first, falls back to Blender if API credits are empty</>
                    ) : null}
                    {workerHints.tripo_api_key_set === false && workerHints.mesh_provider === "tripo" ? (
                      <> (<code>STUDIO_TRIPO_API_KEY</code> not set on worker)</>
                    ) : null}
                  </>
                ) : null}
                . Job order: textures{" "}
                {workerHints.job_textures_before_mesh ? "before" : "after"} mesh (
                <code>STUDIO_JOB_TEXTURES_BEFORE_MESH</code>). Queue consumer:{" "}
                {workerHints.embedded_queue_worker ? (
                  <>
                    <strong>embedded</strong> in this API process (default for SQLite). To reduce load spikes and
                    tunnel 502s during long runs, run a separate <code>immersive-studio queue-worker</code> and set{" "}
                    <code>STUDIO_EMBEDDED_QUEUE_WORKER=0</code> on the API container.
                  </>
                ) : (
                  <>
                    <strong>not embedded</strong> — a dedicated queue worker process should be consuming jobs.
                  </>
                )}
              </p>
              <p className="studio-worker-hints-body">
                Ollama uses NDJSON streaming by default (better read-timeout behavior than one blocking response); set{" "}
                <code>STUDIO_OLLAMA_STREAM=0</code> if your model misbehaves with streaming. The worker retries once
                after a read timeout (2s pause). Optional <code>STUDIO_OLLAMA_NUM_CTX</code> lowers context RAM on
                small hosts. If jobs still fail, prefer mock mode or <code>STUDIO_OLLAMA_DISABLED=1</code> for wiring, a
                faster model, more VM memory, or a higher read timeout (each attempt can block the queue worker for
                that long).
              </p>
            </section>
          ) : null}

          <section className="studio-jobs" aria-labelledby="jobs-heading">
            <div className="studio-jobs-header">
              <h2 id="jobs-heading" className="studio-jobs-title">
                Recent jobs
              </h2>
              <button type="button" className="studio-retry" disabled={!STUDIO_API_READY} onClick={() => void refreshDashboard()}>
                Refresh now
              </button>
            </div>
            {queueSlo && STUDIO_API_READY ? <StudioQueueSloLine q={queueSlo} /> : null}
            {queueSlo &&
            STUDIO_API_READY &&
            (queueSlo.pending_claimable_count > 0 || queueSlo.running_count > 0) &&
            recentJobs.length === 0 ? (
              <p className="studio-queue-slo-warn" role="status">
                Queue has <strong>{queueSlo.pending_claimable_count}</strong> claimable pending and{" "}
                <strong>{queueSlo.running_count}</strong> running but nothing is listed below — click{" "}
                <strong>Refresh now</strong>. Stale <strong>queued</strong> rows usually mean the queue consumer is not
                running (<code>STUDIO_EMBEDDED_QUEUE_WORKER</code> or <code>immersive-studio queue-worker</code>).
              </p>
            ) : null}
            {recentJobs.length === 0 ? (
              <div className="studio-jobs-empty">
                <p className="studio-jobs-empty-title">No jobs in your index yet</p>
                <p className="studio-jobs-empty-body">
                  Run <strong>Run full job</strong> below (try <strong>Mock mode</strong> first to verify the pipeline
                  without Ollama). In-flight queue work appears here as <strong>queued</strong> or <strong>running</strong>{" "}
                  before a pack is written. Failed runs still appear with full error text — expand the error row when
                  present.
                </p>
              </div>
            ) : (
              <div className="studio-table-wrap">
                <p className="studio-jobs-phase-hint">
                  Typical flow: <strong>queued</strong> → worker runs <strong>spec</strong> (Ollama unless mock) →
                  optional <strong>textures</strong> / <strong>mesh</strong> → <strong>pack.zip</strong>.{" "}
                  <code>completed_with_errors</code> means the pack finished but Comfy or mesh reported issues (see
                  error row and download logs).
                </p>
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
                  {recentJobs.map((j) => (
                    <tbody
                      key={j.queue_id ?? j.job_id}
                      className={
                        j.status === "failed" || j.status === "completed_with_errors"
                          ? "studio-jobs-tbody-issue"
                          : undefined
                      }
                    >
                      <tr>
                        <td>
                          <code className="studio-table-mono">{j.created_at}</code>
                        </td>
                        <td>
                          <code>{j.summary}</code>
                          <div className="studio-table-sub">
                            {j.queue_id ? (
                              <>
                                queue <code>{j.queue_id}</code>
                              </>
                            ) : (
                              <code>{j.job_id}</code>
                            )}
                          </div>
                        </td>
                        <td>
                          <span
                            className={
                              j.status === "failed"
                                ? "studio-job-status studio-job-status--bad"
                                : j.status === "completed_with_errors"
                                  ? "studio-job-status studio-job-status--warn"
                                  : j.status === "completed"
                                    ? "studio-job-status studio-job-status--ok"
                                    : "studio-job-status"
                            }
                          >
                            {j.status}
                          </span>
                        </td>
                        <td>{j.has_textures ? "yes" : "no"}</td>
                        <td>
                          {j.queue_id ? (
                            <span className="studio-table-sub">—</span>
                          ) : (
                            <button
                              type="button"
                              className="studio-table-link"
                              disabled={!STUDIO_API_READY}
                              onClick={() => void downloadJobZip(j.job_id)}
                            >
                              ZIP
                            </button>
                          )}
                        </td>
                      </tr>
                      {j.error ? (
                        <tr className="studio-job-error-row">
                          <td colSpan={5}>
                            <div className="studio-job-error-label">Error detail</div>
                            <pre className="studio-job-error-text">{j.error}</pre>
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  ))}
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
