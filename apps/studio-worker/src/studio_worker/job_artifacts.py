"""
Upload finished pack.zip to remote object storage when configured.

`STUDIO_JOB_ARTIFACTS=local` (default): no upload; API serves `pack.zip` from disk.
`s3` / `r2`: S3-compatible `put_object` + presigned GET URL stored on the job index.
`vercel_blob`: HTTP PUT to Vercel Blob API (`BLOB_READ_WRITE_TOKEN`).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from studio_worker import scale_config

try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore[misc, assignment]

_BLOB_API = scale_config.vercel_blob_api_url()


def _boto3_client() -> Any:
    if boto3 is None:
        raise RuntimeError(
            "boto3 is required for STUDIO_JOB_ARTIFACTS=s3 (install optional extra: pip install 'immersive-studio-worker[s3]')"
        )
    kwargs: dict[str, Any] = {"region_name": scale_config.s3_region()}
    ep = scale_config.s3_endpoint_url()
    if ep:
        kwargs["endpoint_url"] = ep
    return boto3.client("s3", **kwargs)  # type: ignore[union-attr]


def _s3_object_key(folder: str) -> str:
    base = scale_config.s3_key_prefix().strip("/")
    safe = folder.replace("\\", "/").lstrip("/")
    return f"{base}/{safe}/pack.zip"


def _upload_vercel_blob(*, pathname: str, data: bytes, content_type: str) -> str:
    token = scale_config.vercel_blob_token()
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is required for STUDIO_JOB_ARTIFACTS=vercel_blob")
    store_tail = token.split("_", 3)[3] if token.count("_") >= 3 else ""
    request_id = f"{store_tail}:{int(time.time() * 1000)}:{time.time_ns():x}"
    q = quote(pathname, safe="")
    url = f"{_BLOB_API}/?pathname={q}"
    headers = {
        "authorization": f"Bearer {token}",
        "x-api-version": scale_config.blob_api_version(),
        "x-content-length": str(len(data)),
        "x-api-blob-request-id": request_id,
        "x-api-blob-request-attempt": "0",
        "x-vercel-blob-access": "public",
        "x-content-type": content_type,
        "x-add-random-suffix": "0",
        "x-allow-overwrite": "1",
    }
    with httpx.Client(timeout=120.0) as client:
        r = client.put(url, content=data, headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"Vercel Blob upload failed ({r.status_code}): {r.text[:500]}")
    body = r.json()
    out = body.get("url") or body.get("downloadUrl")
    if not out:
        raise RuntimeError(f"Vercel Blob upload: unexpected response: {body!r:.300}")
    return str(out)


def _upload_s3(*, key: str, data: bytes, content_type: str) -> str:
    bucket = scale_config.s3_bucket()
    if not bucket:
        raise RuntimeError("STUDIO_S3_BUCKET is required for STUDIO_JOB_ARTIFACTS=s3")
    client = _boto3_client()
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=7 * 24 * 3600,
    )


def upload_pack_zip_if_configured(
    *,
    zip_path: Path,
    job_id: str,
    folder: str,
) -> tuple[str | None, str | None]:
    """
    If remote artifacts are enabled, upload `zip_path` and return `(download_url, backend)`.
    Otherwise `(None, None)` (caller keeps serving from disk).
    """
    backend = scale_config.job_artifacts_backend()
    if backend == "local":
        return None, None
    data = zip_path.read_bytes()
    ct = "application/zip"
    if backend == "vercel_blob":
        pathname = f"{scale_config.s3_key_prefix().strip('/')}/{folder}/pack.zip"
        url = _upload_vercel_blob(pathname=pathname, data=data, content_type=ct)
        return url, "vercel_blob"
    if backend == "s3":
        key = _s3_object_key(folder)
        url = _upload_s3(key=key, data=data, content_type=ct)
        return url, "s3"
    return None, None
