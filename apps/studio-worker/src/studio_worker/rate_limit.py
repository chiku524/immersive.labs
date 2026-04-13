"""Optional sliding-window rate limit for expensive routes (e.g. queue enqueue)."""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict, deque
from time import monotonic
from typing import Deque

from fastapi import HTTPException, Request

from studio_worker.tenant_context import RequestTenant

_lock_buckets: dict[str, Deque[float]] = defaultdict(deque)


def _enqueue_limit_per_minute() -> int:
    raw = os.environ.get("STUDIO_RATE_LIMIT_ENQUEUE_PER_MINUTE", "").strip()
    if not raw:
        return 60
    try:
        n = int(raw, 10)
    except ValueError:
        return 60
    return max(0, min(n, 10_000))


def _bucket_key(request: Request, tenant: RequestTenant) -> str:
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        tok = auth[7:].strip().encode("utf-8", errors="replace")
        return "b:" + hashlib.sha256(tok).hexdigest()[:32]
    xk = (request.headers.get("x-api-key") or "").strip().encode("utf-8", errors="replace")
    if xk:
        return "x:" + hashlib.sha256(xk).hexdigest()[:32]
    tid = (tenant.tenant_id or "").strip() or "anon"
    return "t:" + tid


def check_enqueue_rate_limit(request: Request, tenant: RequestTenant) -> None:
    cap = _enqueue_limit_per_minute()
    if cap <= 0:
        return
    window = 60.0
    key = _bucket_key(request, tenant)
    now = monotonic()
    dq = _lock_buckets[key]
    while dq and dq[0] < now - window:
        dq.popleft()
    if len(dq) >= cap:
        raise HTTPException(
            status_code=429,
            detail=f"Too many enqueue requests (limit {cap} per minute). Retry shortly or raise STUDIO_RATE_LIMIT_ENQUEUE_PER_MINUTE.",
        )
    dq.append(now)
