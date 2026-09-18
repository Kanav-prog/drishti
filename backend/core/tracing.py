"""Request/response tracing middleware and helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from uuid import uuid4

from fastapi import Request

logger = logging.getLogger(__name__)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_or_create_trace_id(request: Request) -> str:
    incoming = request.headers.get("x-trace-id") or request.headers.get("x-request-id")
    return incoming.strip() if incoming else str(uuid4())


async def tracing_middleware(request: Request, call_next):
    trace_id = get_or_create_trace_id(request)
    request.state.trace_id = trace_id

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    request.state.duration_ms = duration_ms
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Response-Time-Ms"] = str(duration_ms)

    logger.info(
        "trace=%s method=%s path=%s status=%s duration_ms=%s",
        trace_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response
