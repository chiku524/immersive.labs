from __future__ import annotations

import os
from pathlib import Path


def studio_worker_package_dir() -> Path:
    """Directory of the installed ``studio_worker`` package (schema, Blender script, Comfy JSON)."""
    return Path(__file__).resolve().parent


def studio_worker_root() -> Path:
    """Backward-compatible alias for :func:`studio_worker_package_dir` (API / attribution)."""
    return studio_worker_package_dir()


def worker_writable_root() -> Path:
    """
    Writable root for jobs, SQLite queue, tenants, and ad-hoc packs.

    Resolution order:

    1. ``STUDIO_WORKER_DATA_DIR`` — explicit directory.
    2. ``STUDIO_REPO_ROOT`` — monorepo layout: ``{STUDIO_REPO_ROOT}/apps/studio-worker/output``.
    3. Default: ``~/.immersive-studio/worker`` (created if missing).
    """
    override = os.environ.get("STUDIO_WORKER_DATA_DIR", "").strip()
    if override:
        p = Path(override).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    rr = os.environ.get("STUDIO_REPO_ROOT", "").strip()
    if rr:
        p = Path(rr).resolve() / "apps" / "studio-worker" / "output"
        p.mkdir(parents=True, exist_ok=True)
        return p
    base = Path.home() / ".immersive-studio" / "worker"
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def asset_spec_schema_path() -> Path:
    return studio_worker_package_dir() / "data" / "studio-asset-spec-v0.1.schema.json"


def blender_export_script_path() -> Path:
    return studio_worker_package_dir() / "blender" / "export_mesh.py"


def comfy_workflows_dir() -> Path:
    return studio_worker_package_dir() / "comfy_workflows"


def jobs_root() -> Path:
    p = worker_writable_root() / "jobs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def job_pack_dir(folder_name: str) -> Path:
    return jobs_root() / folder_name


def queue_db_path() -> Path:
    p = worker_writable_root() / "queue.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def tenants_db_path() -> Path:
    p = worker_writable_root() / "tenants.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def adhoc_pack_dir(output_name: str, *, tenant_id: str | None, scoped_by_tenant: bool) -> Path:
    """
    When scoped_by_tenant (authenticated SaaS), isolate ad-hoc pack folders per workspace.
    """
    root = worker_writable_root()
    if not scoped_by_tenant or not tenant_id:
        return root / output_name
    safe = "".join(c for c in tenant_id if c.isalnum())[:24] or "tenant"
    p = root / "packs" / safe / output_name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
