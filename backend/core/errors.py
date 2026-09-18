"""Structured API errors and exception handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class AppError(Exception):
    """Application-level error with machine-readable code."""

    code: str
    message: str
    status_code: int = 400
    details: dict[str, Any] | None = None


def error_response(
    *,
    code: str,
    message: str,
    status_code: int,
    trace_id: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "trace_id": trace_id,
        }
    }
    if details:
        payload["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=payload)


def register_error_handlers(app) -> None:
    """Register API-wide exception handlers."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        trace_id = getattr(request.state, "trace_id", "unknown")
        return error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            trace_id=trace_id,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        trace_id = getattr(request.state, "trace_id", "unknown")
        return error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            status_code=422,
            trace_id=trace_id,
            details={"errors": exc.errors()},
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        trace_id = getattr(request.state, "trace_id", "unknown")
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return error_response(
            code="HTTP_ERROR",
            message=detail,
            status_code=exc.status_code,
            trace_id=trace_id,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        trace_id = getattr(request.state, "trace_id", "unknown")
        return error_response(
            code="INTERNAL_ERROR",
            message="Unexpected internal server error",
            status_code=500,
            trace_id=trace_id,
            details={"type": type(exc).__name__},
        )
