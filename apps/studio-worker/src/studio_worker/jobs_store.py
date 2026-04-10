from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from studio_worker.paths import job_pack_dir, jobs_root


def _index_path() -> Path:
    p = jobs_root() / "index.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_index() -> dict[str, Any]:
    path = _index_path()
    if not path.is_file():
        return {"jobs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"jobs": []}
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        return {"jobs": []}
    return data


def save_index(data: dict[str, Any]) -> None:
    path = _index_path()
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def new_job_folder_name(job_id: str) -> str:
    short = job_id.replace("-", "")[:10]
    return f"job_{short}"


_SAFE_FOLDER = re.compile(r"[^A-Za-z0-9_.\-]+")


def register_job_entry(
    *,
    job_id: str,
    folder: str,
    summary: str,
    status: str,
    has_textures: bool,
    error: str | None = None,
    tenant_id: str | None = None,
    pack_zip_url: str | None = None,
    pack_artifacts_backend: str | None = None,
) -> dict[str, Any]:
    folder = _SAFE_FOLDER.sub("_", folder)[:120]
    entry = {
        "job_id": job_id,
        "folder": folder,
        "created_at": utc_now_iso(),
        "status": status,
        "summary": summary[:200],
        "has_textures": has_textures,
        "error": error,
        "tenant_id": tenant_id,
    }
    if pack_zip_url:
        entry["pack_zip_url"] = pack_zip_url
    if pack_artifacts_backend:
        entry["pack_artifacts_backend"] = pack_artifacts_backend
    data = load_index()
    jobs: list[dict[str, Any]] = data["jobs"]
    jobs.insert(0, entry)
    max_keep = max(1, int(os.environ.get("STUDIO_JOBS_MAX_COUNT", "200")))
    if len(jobs) > max_keep:
        dropped = jobs[max_keep:]
        for old in dropped:
            f = str(old.get("folder") or "")
            if f:
                shutil.rmtree(job_pack_dir(f), ignore_errors=True)
        jobs = jobs[:max_keep]
    data["jobs"] = jobs
    save_index(data)
    return entry


def count_jobs(
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> int:
    """Number of entries in the job index after tenant filtering."""
    return len(
        list_jobs(
            tenant_id=tenant_id,
            include_legacy_unscoped=include_legacy_unscoped,
        )
    )


def list_jobs(
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = list(load_index().get("jobs", []))
    if tenant_id is None:
        return jobs
    out: list[dict[str, Any]] = []
    for j in jobs:
        tid = j.get("tenant_id")
        if tid == tenant_id:
            out.append(j)
        elif include_legacy_unscoped and tid is None:
            out.append(j)
    return out


def get_job_record(
    job_id: str,
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> dict[str, Any] | None:
    for j in list_jobs():
        if j.get("job_id") != job_id:
            continue
        tid = j.get("tenant_id")
        if tenant_id is None:
            return j
        if tid == tenant_id:
            return j
        if include_legacy_unscoped and tid is None:
            return j
    return None


def find_job_folder(
    job_id: str,
    *,
    tenant_id: str | None = None,
    include_legacy_unscoped: bool = False,
) -> str | None:
    for j in list_jobs():
        if j.get("job_id") != job_id:
            continue
        tid = j.get("tenant_id")
        if tenant_id is None:
            return str(j.get("folder") or "")
        if tid == tenant_id:
            return str(j.get("folder") or "")
        if include_legacy_unscoped and tid is None:
            return str(j.get("folder") or "")
    return None


def allocate_job_id() -> str:
    return str(uuid.uuid4())
