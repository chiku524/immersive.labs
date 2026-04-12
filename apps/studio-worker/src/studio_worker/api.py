from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import FileResponse, RedirectResponse, Response

from studio_worker import tenants_db
from studio_worker.comfy_client import comfy_reachability
from studio_worker.job_runner import run_studio_job
from studio_worker.jobs_store import count_jobs, get_job_record, list_jobs
from studio_worker.attribution import write_pack_attribution
from studio_worker.pack_writer import write_pack
from studio_worker.paths import (
    adhoc_pack_dir,
    job_pack_dir,
    jobs_root,
    queue_db_path,
    studio_worker_root,
    tenants_db_path,
    worker_writable_root,
)
from studio_worker.scale_config import (
    database_url,
    job_artifacts_backend,
    queue_backend,
    redis_queue_engine,
    tenants_backend,
)
from studio_worker import __version__ as studio_worker_package_version
from studio_worker.spec_generate import generate_asset_spec_with_metadata
from studio_worker.sqlite_queue import (
    count_queue_by_status,
    enqueue_job,
    find_queue_id_by_idempotency,
    get_queue_job,
    init_schema as init_queue_schema,
    list_queue_jobs,
    run_worker_loop,
)
from studio_worker.billing_config import stripe_webhook_secret
from studio_worker.billing_routes import router as billing_router
from studio_worker.tenant_context import RequestTenant, api_auth_required, get_request_tenant
from studio_worker.tiers import CREDIT_COST_GENERATE_SPEC, CREDIT_COST_RUN_JOB, CREDIT_COST_RUN_JOB_TEXTURES


def _cors_allow_origins() -> list[str]:
    raw = os.environ.get("STUDIO_CORS_ORIGINS", "").strip()
    if raw == "*":
        return ["*"]
    if raw:
        out: list[str] = []
        for o in raw.split(","):
            x = o.strip()
            if not x:
                continue
            # Browsers send Origin without a trailing slash; tolerate misconfigured env.
            if x != "*":
                x = x.rstrip("/")
            out.append(x)
        return out
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]


def _embedded_queue_worker_enabled() -> bool:
    """
    When true, a daemon thread runs the SQLite/Redis/Postgres queue consumer inside the API process.
    Default ON for sqlite-only deployments (single Docker container on GCE). Set STUDIO_EMBEDDED_QUEUE_WORKER=0
    if you run a dedicated `immersive-studio queue-worker` process.
    """
    raw = os.environ.get("STUDIO_EMBEDDED_QUEUE_WORKER", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    return queue_backend() == "sqlite"


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    tenants_db.init_tenants_schema()
    init_queue_schema()
    if _embedded_queue_worker_enabled():

        def _consume_queue() -> None:
            run_worker_loop(worker_id="api-embedded", poll_interval_s=1.0)

        threading.Thread(
            target=_consume_queue,
            name="studio-queue-consumer",
            daemon=True,
        ).start()
    yield


app = FastAPI(
    title="Immersive Studio Worker",
    version=studio_worker_package_version,
    lifespan=_app_lifespan,
)
app.include_router(billing_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root() -> dict[str, Any]:
    """
    Visiting the API host in a browser hits ``GET /`` (there is no SPA here).
    FastAPI would otherwise return ``{"detail":"Not Found"}`` for an undefined route.
    """
    return {
        "service": "immersive-studio-worker",
        "worker_version": studio_worker_package_version,
        "message": "JSON API — use the paths below (or open /docs for Swagger).",
        "endpoints": {
            "health": "/api/studio/health",
            "openapi": "/openapi.json",
            "docs": "/docs",
            "redoc": "/redoc",
        },
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Browsers request this automatically; avoid noisy 404s in DevTools."""
    return Response(status_code=204)


Category = Literal["prop", "environment_piece", "character_base", "material_library"]
StylePreset = Literal["realistic_hd_pbr", "anime_stylized", "toon_bold"]


class GenerateSpecRequest(BaseModel):
    prompt: str = Field(min_length=1)
    category: Category = "prop"
    style_preset: StylePreset = "toon_bold"
    mock: bool = False


class GenerateSpecResponse(BaseModel):
    spec: dict[str, Any]
    meta: dict[str, Any]


class HealthResponse(BaseModel):
    status: str = "ok"
    auth_required: bool
    stripe_webhook_configured: bool = False
    worker_version: str = Field(
        ...,
        description="Python worker package version (bump + redeploy after server-side fixes).",
    )


class MetricsResponse(BaseModel):
    """Lightweight operator snapshot: queue depth by status + indexed job count."""

    queue: dict[str, int]
    jobs_indexed: int


@app.get("/api/studio/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        auth_required=api_auth_required(),
        stripe_webhook_configured=bool(stripe_webhook_secret()),
        worker_version=studio_worker_package_version,
    )


@app.get("/api/studio/metrics", response_model=MetricsResponse)
def get_metrics(tenant: RequestTenant = Depends(get_request_tenant)) -> MetricsResponse:
    if tenant.limits_enforced:
        q = count_queue_by_status(
            tenant_id=tenant.tenant_id,
            include_legacy_unscoped=False,
        )
        n = count_jobs(
            tenant_id=tenant.tenant_id,
            include_legacy_unscoped=False,
        )
    else:
        q = count_queue_by_status(tenant_id=None)
        n = count_jobs(tenant_id=None)
    return MetricsResponse(queue=q, jobs_indexed=n)


@app.get("/api/studio/comfy-status")
def comfy_status() -> dict[str, Any]:
    return comfy_reachability()


@app.get("/api/studio/usage")
def get_usage(tenant: RequestTenant = Depends(get_request_tenant)) -> dict[str, Any]:
    if not tenant.limits_enforced:
        return {
            "limits_enforced": False,
            "tier_id": tenant.tier_id,
            "tier_name": tenant.tier.display_name,
            "period": None,
            "credits_used": 0,
            "credits_cap": None,
            "credits_generate_spec": CREDIT_COST_GENERATE_SPEC,
            "credits_run_job": CREDIT_COST_RUN_JOB,
            "credits_run_job_textures": CREDIT_COST_RUN_JOB_TEXTURES,
            "textures_allowed": True,
            "max_concurrent_jobs": None,
        }
    used, period = tenants_db.get_usage_row(tenant.tenant_id)
    return {
        "limits_enforced": True,
        "tier_id": tenant.tier_id,
        "tier_name": tenant.tier.display_name,
        "period": period,
        "credits_used": used,
        "credits_cap": tenant.tier.monthly_credits,
        "credits_generate_spec": CREDIT_COST_GENERATE_SPEC,
        "credits_run_job": CREDIT_COST_RUN_JOB,
        "credits_run_job_textures": CREDIT_COST_RUN_JOB_TEXTURES,
        "textures_allowed": tenant.tier.textures_allowed,
        "max_concurrent_jobs": tenant.tier.max_concurrent_jobs,
    }


@app.post("/api/studio/generate-spec", response_model=GenerateSpecResponse)
def post_generate_spec(
    body: GenerateSpecRequest,
    tenant: RequestTenant = Depends(get_request_tenant),
) -> GenerateSpecResponse:
    if tenant.limits_enforced:
        try:
            tenants_db.try_consume_credits(tenant.tenant_id, CREDIT_COST_GENERATE_SPEC)
        except ValueError as e:
            raise HTTPException(status_code=402, detail=str(e)) from e
    try:
        spec, meta = generate_asset_spec_with_metadata(
            user_prompt=body.prompt,
            category=body.category,
            style_preset=body.style_preset,
            use_mock=body.mock,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return GenerateSpecResponse(spec=spec, meta=meta)


class PackRequest(BaseModel):
    spec: dict[str, Any]
    output_name: str = Field(default="StudioPack", pattern=r"^[\w\-]+$")
    unity_urp_hint: str = "6000.0.x LTS (pin when smoke-tested)"
    write_spec_json: bool = True


class PackResponse(BaseModel):
    manifest: dict[str, Any]
    output_dir: str


@app.post("/api/studio/pack", response_model=PackResponse)
def post_pack(
    body: PackRequest,
    tenant: RequestTenant = Depends(get_request_tenant),
) -> PackResponse:
    out = adhoc_pack_dir(
        body.output_name,
        tenant_id=tenant.tenant_id,
        scoped_by_tenant=tenant.limits_enforced,
    )
    try:
        manifest = write_pack(
            out,
            body.spec,
            job_id=None,
            llm_model=None,
            image_pipeline="comfyui:pack-endpoint",
            unity_urp_hint=body.unity_urp_hint,
            write_spec_json=body.write_spec_json,
        )
        write_pack_attribution(out, spec=body.spec, manifest=manifest, meta=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return PackResponse(manifest=manifest, output_dir=str(out))


class RunJobRequest(BaseModel):
    prompt: str = Field(min_length=1)
    category: Category = "prop"
    style_preset: StylePreset = "toon_bold"
    mock: bool = False
    generate_textures: bool = False
    export_mesh: bool = False
    unity_urp_hint: str = "6000.0.x LTS (pin when smoke-tested)"


class RunJobResponse(BaseModel):
    job_id: str
    folder: str
    manifest: dict[str, Any]
    spec: dict[str, Any]
    output_dir: str
    zip_path: str
    texture_logs: list[str]
    mesh_logs: list[str]
    errors: list[str]


class EnqueueJobRequest(BaseModel):
    prompt: str = Field(min_length=1)
    category: Category = "prop"
    style_preset: StylePreset = "toon_bold"
    mock: bool = False
    generate_textures: bool = False
    export_mesh: bool = False
    unity_urp_hint: str = "6000.0.x LTS (pin when smoke-tested)"
    max_attempts: int = Field(default=3, ge=1, le=50)
    comfy_base_url: str | None = None
    idempotency_key: str | None = Field(
        default=None,
        max_length=128,
        description="Optional client key; repeat requests with the same key return the same queue_id without charging credits again.",
    )


class EnqueueJobResponse(BaseModel):
    queue_id: str
    deduplicated: bool = False


@app.post("/api/studio/queue/jobs", response_model=EnqueueJobResponse)
def post_enqueue_job(
    body: EnqueueJobRequest,
    tenant: RequestTenant = Depends(get_request_tenant),
) -> EnqueueJobResponse:
    idem = (body.idempotency_key or "").strip()[:128] or None
    if idem:
        existing = find_queue_id_by_idempotency(tenant.tenant_id, idem)
        if existing:
            return EnqueueJobResponse(queue_id=existing, deduplicated=True)

    cost = 0
    if tenant.limits_enforced:
        if body.generate_textures and not tenant.tier.textures_allowed:
            raise HTTPException(
                status_code=403,
                detail="Texture generation is not included in your subscription tier.",
            )
        cost = (
            CREDIT_COST_RUN_JOB_TEXTURES
            if body.generate_textures
            else CREDIT_COST_RUN_JOB
        )
        try:
            tenants_db.try_consume_credits(tenant.tenant_id, cost)
        except ValueError as e:
            raise HTTPException(status_code=402, detail=str(e)) from e

    payload: dict[str, Any] = {
        "user_prompt": body.prompt,
        "category": body.category,
        "style_preset": body.style_preset,
        "mock": body.mock,
        "generate_textures": body.generate_textures,
        "export_mesh": body.export_mesh,
        "unity_urp_hint": body.unity_urp_hint,
        "tenant_id": tenant.tenant_id,
        "tier_id": tenant.tier_id,
        "limits_enforced": tenant.limits_enforced,
        "credits_precharged": tenant.limits_enforced,
    }
    if body.comfy_base_url is not None:
        payload["comfy_base_url"] = body.comfy_base_url.strip() or None
    out = enqueue_job(
        payload,
        max_attempts=body.max_attempts,
        tenant_id=tenant.tenant_id,
        idempotency_key=idem,
    )
    if out.deduplicated and tenant.limits_enforced and cost > 0:
        tenants_db.refund_credits(tenant.tenant_id, cost)
    return EnqueueJobResponse(queue_id=out.queue_id, deduplicated=out.deduplicated)


@app.get("/api/studio/queue/jobs")
def get_queue_jobs(
    limit: int = 50,
    tenant: RequestTenant = Depends(get_request_tenant),
) -> dict[str, Any]:
    return {
        "jobs": list_queue_jobs(
            limit=limit,
            tenant_id=tenant.tenant_id,
            include_legacy_unscoped=not tenant.limits_enforced,
        )
    }


@app.get("/api/studio/queue/jobs/{queue_id}")
def get_queue_job_by_id(
    queue_id: str,
    tenant: RequestTenant = Depends(get_request_tenant),
) -> dict[str, Any]:
    row = get_queue_job(
        queue_id,
        tenant_id=tenant.tenant_id,
        include_legacy_unscoped=not tenant.limits_enforced,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown queue_id")
    return row


@app.post("/api/studio/jobs/run", response_model=RunJobResponse)
def post_run_job(
    body: RunJobRequest,
    tenant: RequestTenant = Depends(get_request_tenant),
) -> RunJobResponse:
    try:
        result = run_studio_job(
            user_prompt=body.prompt,
            category=body.category,
            style_preset=body.style_preset,
            use_mock=body.mock,
            generate_textures=body.generate_textures,
            unity_urp_hint=body.unity_urp_hint,
            comfy_base_url=None,
            request_tenant=tenant,
            export_mesh=body.export_mesh,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return RunJobResponse(
        job_id=result["job_id"],
        folder=result["folder"],
        manifest=result["manifest"],
        spec=result["spec"],
        output_dir=result["output_dir"],
        zip_path=result["zip_path"],
        texture_logs=result["texture_logs"],
        mesh_logs=result["mesh_logs"],
        errors=result["errors"],
    )


@app.get("/api/studio/jobs")
def get_jobs(tenant: RequestTenant = Depends(get_request_tenant)) -> dict[str, Any]:
    return {
        "jobs": list_jobs(
            tenant_id=tenant.tenant_id,
            include_legacy_unscoped=not tenant.limits_enforced,
        ),
        "jobs_root": str(jobs_root().resolve()),
    }


@app.get("/api/studio/jobs/{job_id}/download", response_model=None)
def download_job_zip(
    job_id: str,
    tenant: RequestTenant = Depends(get_request_tenant),
) -> Response:
    rec = get_job_record(
        job_id,
        tenant_id=tenant.tenant_id,
        include_legacy_unscoped=not tenant.limits_enforced,
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    remote = rec.get("pack_zip_url")
    if isinstance(remote, str) and remote.startswith(("http://", "https://")):
        return RedirectResponse(url=remote, status_code=302)
    folder = str(rec.get("folder") or "")
    if not folder:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    zip_path = job_pack_dir(folder) / "pack.zip"
    if not zip_path.is_file():
        raise HTTPException(status_code=404, detail="pack.zip missing — re-run job")
    return FileResponse(
        path=str(zip_path),
        filename=f"immersive-studio-{job_id}.zip",
        media_type="application/zip",
    )


@app.get("/api/studio/paths")
def studio_paths(tenant: RequestTenant = Depends(get_request_tenant)) -> dict[str, str]:
    return {
        "jobs_root": str(jobs_root().resolve()),
        "studio_worker_root": str(studio_worker_root().resolve()),
        "worker_data_root": str(worker_writable_root().resolve()),
        "queue_db": str(queue_db_path().resolve()),
        "tenants_db": str(tenants_db_path().resolve()),
        "queue_backend": queue_backend(),
        "redis_queue_engine": redis_queue_engine() if queue_backend() == "redis" else "",
        "tenants_backend": tenants_backend(),
        "job_artifacts_backend": job_artifacts_backend(),
        "postgres_configured": "1" if database_url() else "0",
    }
