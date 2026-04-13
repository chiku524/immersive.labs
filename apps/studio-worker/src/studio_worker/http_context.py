"""HTTP request context: correlation id + access log for operators."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_access = logging.getLogger("studio.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign ``X-Request-Id`` (or echo client value) and log one structured line per request."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        rid = (request.headers.get("x-request-id") or "").strip() or str(uuid.uuid4())
        request.state.request_id = rid
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            ms = (time.perf_counter() - t0) * 1000.0
            _access.exception(
                "request_error method=%s path=%s request_id=%s elapsed_ms=%.1f",
                request.method,
                request.url.path,
                rid,
                ms,
            )
            raise
        ms = (time.perf_counter() - t0) * 1000.0
        _access.info(
            "request method=%s path=%s status=%s request_id=%s elapsed_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            rid,
            ms,
        )
        response.headers.setdefault("X-Request-Id", rid)
        return response
