from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    override = os.environ.get("STUDIO_REPO_ROOT")
    if override:
        return Path(override).resolve()
    # src/studio_worker/paths.py -> …/apps/studio-worker -> …/repo root
    return Path(__file__).resolve().parents[4]


def asset_spec_schema_path() -> Path:
    return (
        repo_root()
        / "packages"
        / "studio-types"
        / "schema"
        / "studio-asset-spec-v0.1.schema.json"
    )


def studio_worker_root() -> Path:
    return repo_root() / "apps" / "studio-worker"


def blender_export_script_path() -> Path:
    return studio_worker_root() / "blender" / "export_mesh.py"


def comfy_workflows_dir() -> Path:
    return studio_worker_root() / "comfy" / "workflows"


def jobs_root() -> Path:
    return studio_worker_root() / "output" / "jobs"


def job_pack_dir(folder_name: str) -> Path:
    return jobs_root() / folder_name


def queue_db_path() -> Path:
    p = studio_worker_root() / "output" / "queue.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def tenants_db_path() -> Path:
    p = studio_worker_root() / "output" / "tenants.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def adhoc_pack_dir(output_name: str, *, tenant_id: str | None, scoped_by_tenant: bool) -> Path:
    """
    When scoped_by_tenant (authenticated SaaS), isolate ad-hoc pack folders per workspace.
    """
    root = studio_worker_root() / "output"
    if not scoped_by_tenant or not tenant_id:
        return root / output_name
    safe = "".join(c for c in tenant_id if c.isalnum())[:24] or "tenant"
    p = root / "packs" / safe / output_name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
