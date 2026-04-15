/**
 * Shared TypeScript shapes for the Video Game Generation Studio pipeline.
 * Keep in sync with docs/studio/json-schema-spec.md.
 */

export type StudioStylePreset =
  | "realistic_hd_pbr"
  | "anime_stylized"
  | "toon_bold";

export type StudioAssetCategory =
  | "prop"
  | "environment_piece"
  | "character_base"
  | "material_library";

export interface StudioMaterialSlot {
  id: string;
  role: "albedo" | "normal" | "orm" | "emissive" | "mask";
  resolution_hint: 512 | 1024 | 2048 | 4096;
  notes?: string;
}

export interface StudioAssetVariant {
  variant_id: string;
  label: string;
  seed?: number;
}

export interface StudioAssetSpec {
  spec_version: "0.1";
  asset_id: string;
  display_name: string;
  category: StudioAssetCategory;
  style_preset: StudioStylePreset;
  poly_budget_tris: number;
  /** World units: 1 unit = 1 meter in Unity convention. */
  target_height_m?: number;
  palette?: string[];
  tags: string[];
  material_slots: StudioMaterialSlot[];
  variants: StudioAssetVariant[];
  generation: {
    source_prompt: string;
    negative_prompt?: string;
    /** References to locked style assets (paths or hashes). */
    reference_assets?: string[];
  };
  unity: {
    import_subfolder: string;
    collider: "box" | "capsule" | "mesh_convex" | "none";
  };
}

export interface StudioJobManifest {
  manifest_version: "0.1";
  job_id: string;
  created_at: string;
  engine_target: "unity";
  assets: StudioAssetSpec[];
  toolchain: {
    llm_model?: string;
    image_pipeline?: string;
    mesh_pipeline?: string;
  };
}

// --- HTTP API JSON (worker FastAPI) — keep aligned with studio_dashboard + api routes ---

/** Row from `GET /api/studio/jobs` → `jobs[]`. */
export interface StudioJobSummary {
  job_id: string;
  folder: string;
  created_at: string;
  status: string;
  summary: string;
  has_textures: boolean;
  error: string | null;
}

/** `GET /api/studio/usage` and `dashboard.usage`. */
export interface StudioUsageInfo {
  limits_enforced: boolean;
  tier_id: string;
  tier_name: string;
  period: string | null;
  credits_used: number;
  credits_cap: number | null;
  /** Present when worker returns credit pricing hints (optional in UI). */
  credits_generate_spec?: number;
  credits_run_job?: number;
  credits_run_job_textures?: number;
  textures_allowed: boolean;
  max_concurrent_jobs: number | null;
}

/** `GET /api/studio/billing/status` and `dashboard.billing`. */
export interface StudioBillingStatus {
  stripe_checkout_available: boolean;
  checkout_tiers: string[];
  portal_needs_customer?: boolean;
  stripe_customer_linked: boolean;
  stripe_subscription_id: string | null;
  tier_id: string;
}

/** `GET /api/studio/jobs` body (also nested as `dashboard.jobs`). */
export interface StudioJobsListPayload {
  jobs: StudioJobSummary[];
  jobs_root: string;
}

/** `GET /api/studio/dashboard` → `worker_hints` (operator tuning, not secrets). */
export interface StudioWorkerHints {
  ollama_read_timeout_s: number;
  /** Upper bound for read timeout env and second attempt (worker ≥ 0.1.7). */
  ollama_read_timeout_max_s?: number;
  ollama_model: string;
  ollama_base_url: string;
  /** Ollama ``/api/chat`` uses NDJSON streaming unless disabled via env (worker ≥ current). */
  ollama_stream_enabled?: boolean;
  /** Ollama ``options.num_predict`` cap for spec generation. */
  ollama_num_predict?: number;
  /** Per-image ComfyUI wait (seconds), from ``STUDIO_COMFY_IMAGE_WAIT_S``. */
  comfy_image_wait_s?: number;
  /** Parallel ComfyUI texture requests per job (``STUDIO_COMFY_MAX_CONCURRENT``). */
  comfy_max_concurrent?: number;
  /** When true, the SQLite queue consumer runs inside the API process. */
  embedded_queue_worker: boolean;
  /** When true, texture pass runs before Blender mesh export (``STUDIO_JOB_TEXTURES_BEFORE_MESH``). */
  job_textures_before_mesh?: boolean;
  /** Global cap on texture width/height (``STUDIO_TEXTURE_MAX_SIDE``). */
  texture_global_max_side?: number;
  /** Effective queue driver: sqlite, postgres, redis, sqs. */
  queue_backend?: string;
  postgres_configured?: boolean;
  redis_configured?: boolean;
}

/** `GET /api/studio/dashboard` → `queue_slo` (matches ``GET /api/studio/metrics`` → ``slo``). */
export interface StudioQueueSloSnapshot {
  pending_oldest_age_seconds: number | null;
  running_oldest_age_seconds: number | null;
  pending_claimable_count: number;
  running_count: number;
}

/** `GET /api/studio/dashboard` — bundles usage + billing + jobs for one round-trip. */
export interface StudioDashboardPayload {
  usage: StudioUsageInfo;
  billing: StudioBillingStatus;
  jobs: StudioJobsListPayload;
  worker_hints?: StudioWorkerHints;
  queue_slo?: StudioQueueSloSnapshot;
}

/** `GET /api/studio/comfy-status`. */
export interface StudioComfyStatusPayload {
  reachable: boolean;
  url: string;
  detail: string | null;
}
