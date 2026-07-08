from __future__ import annotations

import json
import logging
import shutil
from typing import TYPE_CHECKING, Any

from studio_worker.attribution import write_pack_attribution
from studio_worker.job_artifacts import upload_pack_zip_if_configured
from studio_worker.jobs_store import allocate_job_id, new_job_folder_name, register_job_entry
from studio_worker.ollama_client import ollama_model
from studio_worker.pack_diagnostics import build_pack_diagnostics
from studio_worker.pack_writer import append_godot_diagnostics_notes, write_pack
from studio_worker.paths import job_pack_dir
from studio_worker.quotas import enforce_quota_before_new_job
from studio_worker.spec_generate import generate_asset_spec_with_metadata
from studio_worker import tenants_db
from studio_worker.mesh_export import apply_mesh_toolchain_to_manifest, export_mesh_default_from_env, run_blender_bind_pack_textures
from studio_worker.mesh_pipeline.config import texture_source, tripo_texture_enabled
from studio_worker.mesh_pipeline.runner import FALLBACK_PIPELINE_ID, try_export_mesh_for_pack
from studio_worker.scale_config import job_textures_before_mesh
from studio_worker.texture_pipeline import comfy_profile, generate_pbr_textures_for_spec
from studio_worker.tiers import CREDIT_COST_RUN_JOB, CREDIT_COST_RUN_JOB_TEXTURES
from studio_worker.zip_pack import zip_directory

if TYPE_CHECKING:
    from studio_worker.tenant_context import RequestTenant

_log = logging.getLogger("studio.job")


def run_studio_job(
    *,
    user_prompt: str,
    use_mock: bool,
    generate_textures: bool,
    unity_urp_hint: str,
    comfy_base_url: str | None = None,
    request_tenant: RequestTenant | None = None,
    export_mesh: bool = False,
    queue_id: str | None = None,
    engine_target: str = "unity",
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
            "job_begin job_id=%s folder=%s mock=%s textures=%s export_mesh=%s engine_target=%s",
            job_id,
            folder,
            use_mock,
            generate_textures,
            export_mesh,
            engine_target,
        )

        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if queue_id:
            try:
                from studio_worker.sqlite_queue import update_queue_job_progress

                update_queue_job_progress(
                    queue_id,
                    {"phase": "spec", "label": "Generating asset spec…"},
                )
            except Exception:
                _log.debug("queue_progress_spec_skip queue_id=%s", queue_id, exc_info=True)

        errors: list[str] = []
        texture_logs: list[str] = []
        mesh_logs: list[str] = []
        has_textures = False

        try:
            spec, meta = generate_asset_spec_with_metadata(
                user_prompt=user_prompt,
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
        tex_src = texture_source()
        prof = comfy_profile()
        if tex_src == "tripo":
            image_pipeline = "tripo:baked_pbr_v1"
            if generate_textures:
                image_pipeline = "tripo:baked_pbr_v1+requested"
        elif tex_src == "comfy":
            image_pipeline = f"comfyui:{prof}_pbr_v1"
            if generate_textures:
                image_pipeline = f"comfyui:{prof}_pbr_v1+run"
        else:
            image_pipeline = "none"

        manifest = write_pack(
            out_dir,
            spec,
            job_id=job_id,
            llm_model=llm_label,
            image_pipeline=image_pipeline,
            unity_urp_hint=unity_urp_hint,
            write_spec_json=True,
            engine_target=engine_target,
        )

        do_mesh = bool(export_mesh) or export_mesh_default_from_env()
        tex_first = job_textures_before_mesh()
        use_comfy_textures = generate_textures and tex_src == "comfy"

        def _tripo_mesh_textures() -> bool | None:
            if tex_src == "tripo":
                return generate_textures
            if tex_src == "comfy":
                return False
            return tripo_texture_enabled() if generate_textures else False

        def _mesh_step() -> None:
            nonlocal mesh_logs, errors, manifest, image_pipeline
            m_ok_logs, m_errs, pipeline_id = try_export_mesh_for_pack(
                out_dir,
                spec,
                mesh_textures=_tripo_mesh_textures(),
            )
            mesh_logs.extend(m_ok_logs)
            errors.extend(m_errs)
            apply_mesh_toolchain_to_manifest(
                manifest,
                ok=len(m_errs) == 0 and len(m_ok_logs) > 0,
                pipeline_id=pipeline_id,
            )
            if (
                tex_src == "tripo"
                and generate_textures
                and len(m_errs) == 0
                and len(m_ok_logs) > 0
                and pipeline_id != FALLBACK_PIPELINE_ID
            ):
                image_pipeline = "tripo:baked_pbr_v1+ok"
            elif tex_src == "tripo" and generate_textures and pipeline_id == FALLBACK_PIPELINE_ID:
                image_pipeline = "tripo:baked_pbr_v1+fallback_blender"
            if tex_src == "tripo" and generate_textures and (
                pipeline_id == FALLBACK_PIPELINE_ID
                or (len(m_errs) == 0 and len(m_ok_logs) > 0)
            ):
                manifest["toolchain"]["image_pipeline"] = image_pipeline
            (out_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

        def _texture_step() -> None:
            nonlocal texture_logs, has_textures, errors, manifest
            try:
                written, texture_logs = generate_pbr_textures_for_spec(
                    spec,
                    out_dir,
                    base_url=comfy_base_url,
                    queue_id=queue_id,
                )
                has_textures = len(written) > 0
                manifest["toolchain"]["image_pipeline"] = f"comfyui:{prof}_pbr_v1+ok"
                (out_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                )
            except Exception as e:
                errors.append(str(e))
                has_textures = False
                manifest["toolchain"]["image_pipeline"] = f"comfyui:error:{str(e)}"[:4000]
                (out_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                )

        if tex_first:
            if use_comfy_textures:
                _texture_step()
            if do_mesh:
                _mesh_step()
        else:
            if do_mesh:
                _mesh_step()
            if use_comfy_textures:
                _texture_step()

        texture_bind_logs: list[str] = []
        texture_bind_errors: list[str] = []
        if do_mesh and use_comfy_textures:
            bind_logs, bind_errs = run_blender_bind_pack_textures(pack_root=out_dir, spec=spec)
            texture_bind_logs = bind_logs
            texture_bind_errors = bind_errs
            texture_logs.extend(bind_logs)
            errors.extend(bind_errs)
            if bind_logs:
                manifest["toolchain"]["texture_bind"] = "blender:bind_pbr_textures.py+ok"
            elif bind_errs:
                manifest["toolchain"]["texture_bind"] = "blender:bind_pbr_textures.py+skip"
            else:
                manifest["toolchain"]["texture_bind"] = "blender:bind_pbr_textures.py+missing"
            (out_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

        diagnostics = build_pack_diagnostics(
            spec=spec,
            pack_root=out_dir,
            generate_textures=generate_textures,
            export_mesh=do_mesh,
            mesh_pipeline=str((manifest.get("toolchain") or {}).get("mesh_pipeline", "")),
            image_pipeline=str((manifest.get("toolchain") or {}).get("image_pipeline", "")),
            texture_bind_logs=texture_bind_logs,
            texture_bind_errors=texture_bind_errors,
            texture_source=tex_src,
        )
        (out_dir / "pack_diagnostics.json").write_text(
            json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8"
        )
        if diagnostics.get("notes"):
            append_godot_diagnostics_notes(out_dir, diagnostics["notes"])

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
                    "engine_target": manifest.get("engine_target", engine_target),
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
