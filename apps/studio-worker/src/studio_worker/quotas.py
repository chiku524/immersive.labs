from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from studio_worker.jobs_store import load_index, save_index
from studio_worker.paths import job_pack_dir, jobs_root


def _dir_total_bytes(root: Path) -> int:
    total = 0
    if not root.is_dir():
        return 0
    for p in root.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                continue
    return total


def jobs_total_bytes() -> int:
    return _dir_total_bytes(jobs_root())


def max_jobs_count() -> int:
    return max(1, int(os.environ.get("STUDIO_JOBS_MAX_COUNT", "200")))


def max_jobs_total_bytes() -> int:
    return int(os.environ.get("STUDIO_JOBS_MAX_TOTAL_BYTES", str(5 * 1024**3)))


def _delete_job_folder(folder: str) -> None:
    p = job_pack_dir(folder)
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)


def prune_oldest_jobs(*, max_count: int | None = None, max_total_bytes: int | None = None) -> list[str]:
    """
    Remove oldest job folders (tail of index) until within limits. Returns deleted folder names.
    """
    max_count = max_count if max_count is not None else max_jobs_count()
    max_total_bytes = max_total_bytes if max_total_bytes is not None else max_jobs_total_bytes()

    data = load_index()
    jobs: list[dict[str, Any]] = list(data.get("jobs", []))
    removed: list[str] = []

    def delete_last() -> None:
        if not jobs:
            return
        old = jobs.pop()
        folder = str(old.get("folder") or "")
        if folder:
            _delete_job_folder(folder)
            removed.append(folder)

    while len(jobs) > max_count:
        delete_last()

    while jobs and jobs_total_bytes() > max_total_bytes:
        delete_last()

    data["jobs"] = jobs
    save_index(data)
    return removed


def enforce_quota_before_new_job() -> None:
    if os.environ.get("STUDIO_QUOTAS_DISABLED", "").lower() in ("1", "true", "yes"):
        return
    prune_oldest_jobs(max_count=max_jobs_count(), max_total_bytes=max_jobs_total_bytes())
    if jobs_total_bytes() > max_jobs_total_bytes():
        raise ValueError(
            "Studio jobs disk quota exceeded (STUDIO_JOBS_MAX_TOTAL_BYTES). "
            "Delete packs under output/jobs/ or raise the limit."
        )
