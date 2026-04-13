"""
Environment-driven backends for horizontal scale (Postgres, object storage).

Defaults preserve single-VM SQLite + local disk behavior.
"""

from __future__ import annotations

import os


def database_url() -> str | None:
    """Postgres URL (Vercel Postgres, Neon, RDS, …). `postgresql://` or `postgres://`."""
    u = os.environ.get("DATABASE_URL", "").strip()
    return u or None


def redis_url() -> str | None:
    u = os.environ.get("STUDIO_REDIS_URL", "").strip() or os.environ.get("REDIS_URL", "").strip()
    return u or None


def redis_queue_prefix() -> str:
    p = os.environ.get("STUDIO_REDIS_QUEUE_PREFIX", "studio:q").strip()
    return p if p else "studio:q"


def redis_queue_max_timeline() -> int:
    try:
        return max(100, int(os.environ.get("STUDIO_REDIS_QUEUE_MAX_TIMELINE", "5000")))
    except ValueError:
        return 5000


def redis_queue_engine() -> str:
    """
    When `STUDIO_QUEUE_BACKEND=redis`: `zset` (sorted-set dispatch, default) or `streams`
    (Redis Streams + consumer group / XREADGROUP).
    """
    e = os.environ.get("STUDIO_REDIS_QUEUE_ENGINE", "zset").strip().lower()
    if e in ("stream", "streams", "xreadgroup", "xgroup"):
        return "streams"
    return "zset"


def redis_queue_streams_prefix() -> str:
    """Isolated key namespace for `STUDIO_REDIS_QUEUE_ENGINE=streams` (avoid colliding with zset keys)."""
    p = os.environ.get("STUDIO_REDIS_STREAMS_PREFIX", "").strip()
    if p:
        return p
    return f"{redis_queue_prefix()}:sx"


def redis_stream_group() -> str:
    g = os.environ.get("STUDIO_REDIS_STREAM_GROUP", "studio_workers").strip()
    return g if g else "studio_workers"


def redis_streams_read_block_ms() -> int:
    try:
        return max(50, min(30000, int(os.environ.get("STUDIO_REDIS_STREAM_BLOCK_MS", "5000"))))
    except ValueError:
        return 5000


def redis_streams_maxlen() -> int:
    try:
        return max(1000, int(os.environ.get("STUDIO_REDIS_STREAM_MAXLEN", "50000")))
    except ValueError:
        return 50000


def sqs_queue_url() -> str | None:
    return os.environ.get("STUDIO_SQS_QUEUE_URL", "").strip() or None


def sqs_endpoint_url() -> str | None:
    u = os.environ.get("STUDIO_SQS_ENDPOINT_URL", "").strip()
    return u or None


def sqs_wait_seconds() -> int:
    try:
        return max(0, min(20, int(os.environ.get("STUDIO_SQS_WAIT_SECONDS", "20"))))
    except ValueError:
        return 20


def sqs_visibility_timeout() -> int:
    try:
        return max(30, int(os.environ.get("STUDIO_SQS_VISIBILITY_TIMEOUT", "900")))
    except ValueError:
        return 900


def aws_region() -> str:
    return os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")).strip() or "us-east-1"


def queue_backend() -> str:
    """
    `sqlite` (default), `postgres` (DATABASE_URL), `redis` (STUDIO_REDIS_URL / REDIS_URL),
    or `sqs` (STUDIO_SQS_QUEUE_URL + DATABASE_URL — Postgres holds job rows, SQS wakes workers).
    """
    b = os.environ.get("STUDIO_QUEUE_BACKEND", "").strip().lower()
    if b == "redis" and redis_url():
        return "redis"
    if b == "sqs" and sqs_queue_url() and database_url():
        return "sqs"
    if b == "postgres" and database_url():
        return "postgres"
    return "sqlite"


def tenants_backend() -> str:
    """
    `sqlite` (default) or `postgres` (requires DATABASE_URL).
    """
    b = os.environ.get("STUDIO_TENANTS_BACKEND", "").strip().lower()
    if b == "postgres" and database_url():
        return "postgres"
    return "sqlite"


def job_artifacts_backend() -> str:
    """
    `local` (default) — pack.zip on disk under jobs_root.
    `s3` — upload after zip; download streams from S3-compatible API.
    `vercel_blob` — upload via Vercel Blob HTTP API (token env).
    """
    b = os.environ.get("STUDIO_JOB_ARTIFACTS", "").strip().lower()
    if b in ("s3", "vercel_blob", "r2"):
        return "s3" if b == "r2" else b
    return "local"


def s3_endpoint_url() -> str | None:
    """Optional custom endpoint (Cloudflare R2, MinIO)."""
    u = os.environ.get("STUDIO_S3_ENDPOINT_URL", "").strip()
    return u or None


def s3_bucket() -> str | None:
    return os.environ.get("STUDIO_S3_BUCKET", "").strip() or None


def s3_region() -> str:
    return os.environ.get("STUDIO_S3_REGION", "auto").strip() or "auto"


def vercel_blob_token() -> str | None:
    return os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip() or None


def s3_key_prefix() -> str:
    """Logical prefix for pack objects (no leading/trailing slashes)."""
    raw = os.environ.get("STUDIO_S3_KEY_PREFIX", "immersive-studio/packs").strip().strip("/")
    return raw or "immersive-studio/packs"


def vercel_blob_api_url() -> str:
    return os.environ.get("VERCEL_BLOB_API_URL", "https://vercel.com/api/blob").rstrip("/")


def blob_api_version() -> str:
    return os.environ.get("VERCEL_BLOB_API_VERSION", "12").strip() or "12"


def embedded_queue_worker_enabled() -> bool:
    """
    When true, the API process runs an embedded SQLite queue consumer thread.
    Mirrors ``STUDIO_EMBEDDED_QUEUE_WORKER`` + ``STUDIO_QUEUE_BACKEND`` (see ``api`` lifespan).
    """
    raw = os.environ.get("STUDIO_EMBEDDED_QUEUE_WORKER", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    return queue_backend() == "sqlite"
