from __future__ import annotations

import json
import logging
import shutil
from typing import TYPE_CHECKING, Any

from studio_worker.attribution import write_pack_attribution
from studio_worker.job_artifacts import upload_pack_zip_if_configured
from studio_worker.jobs_store import allocate_job_id, new_job_folder_name, register_job_entry
from studio_worker.ollama_client import ollama_model
from studio_worker.pack_writer import write_pack
from studio_worker.paths import job_pack_dir
from studio_worker.quotas import enforce_quota_before_new_job
from studio_worker.spec_generate import generate_asset_spec_with_metadata
from studio_worker import tenants_db
from studio_worker.mesh_export import (
    apply_mesh_toolchain_to_manifest,
    export_mesh_default_from_env,
    try_export_placeholder_for_pack,
)
from studio_worker.texture_pipeline import comfy_profile, generate_pbr_textures_for_spec
from studio_worker.tiers import CREDIT_COST_RUN_JOB, CREDIT_COST_RUN_JOB_TEXTURES
from studio_worker.zip_pack import zip_directory

if TYPE_CHECKING:
    from studio_worker.tenant_context import RequestTenant

_log = logging.getLogger("studio.job")


def run_studio_job(
    *,
    user_prompt: str,
    category: str,
    style_preset: str,
    use_mock: bool,
    generate_textures: bool,
    unity_urp_hint: str,
    comfy_base_url: str | None = None,
    request_tenant: RequestTenant | None = None,
    export_mesh: bool = False,
) -> dict[str, Any]:
    rt: RequestTenant | None = request_tenant
    slot_held = False
    tenant_id_for_jobs: str | None = rt.tenant_id if rt else None

    try:
        if rt and rt.limits_enforced:
            if generate_textures and not rt.tier.textures_allowed:
                raise ValueError(
                    "GPU texture generation is not included in your subscription tier. "
                    "Upgrade to Indie or Small team, or disable texture generation."
                )
            tenants_db.try_acquire_job_slot(rt.tenant_id, rt.tier.max_concurrent_jobs)
            slot_held = True
            if not rt.credits_precharged:
                cost = (
                    CREDIT_COST_RUN_JOB_TEXTURES
                    if generate_textures
                    else CREDIT_COST_RUN_JOB
                )
                tenants_db.try_consume_credits(rt.tenant_id, cost)

        enforce_quota_before_new_job()

        job_id = allocate_job_id()
        folder = new_job_folder_name(job_id)
        out_dir = job_pack_dir(folder)
        _log.info(
            "job_begin job_id=%s folder=%s mock=%s textures=%s export_mesh=%s",
            job_id,
            folder,
            use_mock,
            generate_textures,
            export_mesh,
        )

        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        errors: list[str] = []
        texture_logs: list[str] = []
        mesh_logs: list[str] = []
        has_textures = False

        try:
            spec, meta = generate_asset_spec_with_metadata(
                user_prompt=user_prompt,
                category=category,
                style_preset=style_preset,
                use_mock=use_mock,
            )
        except Exception as e:
            _log.warning("job_spec_failed job_id=%s err=%s", job_id, e)
            register_job_entry(
                job_id=job_id,
                folder=folder,
                summary="(spec failed)",
                status="failed",
                has_textures=False,
                error=str(e),
                tenant_id=tenant_id_for_jobs,
            )
            raise

        llm_label = None if use_mock else f"ollama:{ollama_model()}"
        _log.info("job_spec_ok job_id=%s asset_id=%s llm=%s", job_id, spec.get("asset_id"), llm_label)
        prof = comfy_profile()
        image_pipeline = f"comfyui:{prof}_pbr_v1"
        if generate_textures:
            image_pipeline = f"comfyui:{prof}_pbr_v1+run"

        manifest = write_pack(
            out_dir,
            spec,
            job_id=job_id,
            llm_model=llm_label,
            image_pipeline=image_pipeline,
            unity_urp_hint=unity_urp_hint,
            write_spec_json=True,
        )

        do_mesh = bool(export_mesh) or export_mesh_default_from_env()
        if do_mesh:
            m_ok_logs, m_errs = try_export_placeholder_for_pack(out_dir, spec)
            mesh_logs.extend(m_ok_logs)
            errors.extend(m_errs)
            apply_mesh_toolchain_to_manifest(manifest, ok=len(m_errs) == 0 and len(m_ok_logs) > 0)
            (out_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

        if generate_textures:
            try:
                written, texture_logs = generate_pbr_textures_for_spec(
                    spec, out_dir, base_url=comfy_base_url
                )
                has_textures = len(written) > 0
                manifest["toolchain"]["image_pipeline"] = f"comfyui:{prof}_pbr_v1+ok"
                (out_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                )
            except Exception as e:
                errors.append(str(e))
                has_textures = False
                # Keep enough of the message for Comfy JSON (node_errors); 200 chars was too short for zip review.
                manifest["toolchain"]["image_pipeline"] = f"comfyui:error:{str(e)}"[:4000]
                (out_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                )

        write_pack_attribution(out_dir, spec=spec, manifest=manifest, meta=meta)

        zip_path = out_dir / "pack.zip"
        zip_directory(out_dir, zip_path)

        pack_url, pack_backend = upload_pack_zip_if_configured(
            zip_path=zip_path, job_id=job_id, folder=folder
        )

        (out_dir / "job_meta.json").write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "folder": folder,
                    "tenant_id": tenant_id_for_jobs,
                    "texture_logs": texture_logs,
                    "mesh_logs": mesh_logs,
                    "errors": errors,
                    "moderation": "enabled",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        status = "completed" if not errors else "completed_with_errors"
        _log.info("job_complete job_id=%s status=%s errors=%s", job_id, status, len(errors))
        register_job_entry(
            job_id=job_id,
            folder=folder,
            summary=str(spec.get("asset_id", "asset")),
            status=status,
            has_textures=has_textures,
            error="; ".join(errors) if errors else None,
            tenant_id=tenant_id_for_jobs,
            pack_zip_url=pack_url,
            pack_artifacts_backend=pack_backend,
        )

        return {
            "job_id": job_id,
            "folder": folder,
            "manifest": manifest,
            "spec": spec,
            "output_dir": str(out_dir.resolve()),
            "zip_path": str(zip_path.resolve()),
            "texture_logs": texture_logs,
            "mesh_logs": mesh_logs,
            "errors": errors,
        }
    finally:
        if slot_held and rt:
            tenants_db.release_job_slot(rt.tenant_id)
