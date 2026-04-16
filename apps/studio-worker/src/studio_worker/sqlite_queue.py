"""
Job queue: SQLite (default), Postgres, Redis, or SQS+Postgres.

Backends are loaded lazily so the default install does not require `psycopg`, `redis`, or `boto3`.
"""

from __future__ import annotations

from studio_worker.paths import queue_db_path
from studio_worker.scale_config import queue_backend, redis_queue_engine

_backend = queue_backend()

if _backend == "postgres":
    from studio_worker import queue_postgres as _qb
elif _backend == "redis":
    if redis_queue_engine() == "streams":
        from studio_worker import queue_redis_streams as _qb
    else:
        from studio_worker import queue_redis as _qb
elif _backend == "sqs":
    from studio_worker import queue_sqs_postgres as _qb
else:
    from studio_worker import queue_sqlite as _qb

EnqueueOutcome = _qb.EnqueueOutcome
QueueWorkerConfig = _qb.QueueWorkerConfig
claim_next_job = _qb.claim_next_job
count_queue_by_status = _qb.count_queue_by_status
enqueue_job = _qb.enqueue_job
find_queue_id_by_idempotency = _qb.find_queue_id_by_idempotency
get_queue_job = _qb.get_queue_job
init_schema = _qb.init_schema
list_queue_jobs = _qb.list_queue_jobs
mark_completed = _qb.mark_completed
mark_failed = _qb.mark_failed
run_worker_loop = _qb.run_worker_loop
update_queue_job_progress = _qb.update_queue_job_progress

if _backend == "sqlite":
    queue_slo_hints = _qb.queue_slo_hints
    reclaim_stale_running_jobs = _qb.reclaim_stale_running_jobs
else:

    def reclaim_stale_running_jobs() -> int:
        return 0

    def queue_slo_hints(
        *,
        tenant_id: str | None = None,
        include_legacy_unscoped: bool = False,
    ) -> dict[str, object]:
        """Non-SQLite backends: ages unknown here; use queue metrics + external store."""
        return {
            "pending_oldest_age_seconds": None,
            "running_oldest_age_seconds": None,
            "pending_claimable_count": 0,
            "running_count": 0,
        }


__all__ = [
    "EnqueueOutcome",
    "QueueWorkerConfig",
    "claim_next_job",
    "count_queue_by_status",
    "enqueue_job",
    "find_queue_id_by_idempotency",
    "get_queue_job",
    "init_schema",
    "list_queue_jobs",
    "mark_completed",
    "mark_failed",
    "queue_db_path",
    "run_worker_loop",
    "queue_slo_hints",
    "reclaim_stale_running_jobs",
    "update_queue_job_progress",
]
