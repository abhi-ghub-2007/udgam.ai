"""The single error envelope (API_CONTRACT section 0).

Every non-2xx response has the same shape, so js/core/api.js has exactly one
unwrapping path. A 503 from a missing integration key never names the
environment variable (A-15).
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("udgam.errors")


class AppError(Exception):
    """Raised by routers and services. Carries an API_CONTRACT error code."""

    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None,
                 status_code: int | None = None, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class Unauthenticated(AppError):
    status_code, code = 401, "UNAUTHENTICATED"


class Forbidden(AppError):
    status_code, code = 403, "FORBIDDEN"


class NotFound(AppError):
    status_code, code = 404, "NOT_FOUND"


class ValidationFailed(AppError):
    status_code, code = 422, "VALIDATION_ERROR"


class InvalidStateTransition(AppError):
    status_code, code = 409, "INVALID_STATE_TRANSITION"


class Duplicate(AppError):
    status_code, code = 409, "DUPLICATE"


class UpstreamUnavailable(AppError):
    status_code, code = 503, "UPSTREAM_UNAVAILABLE"


def envelope(code: str, message: str, field: str | None = None) -> dict:
    return {"error": {"code": code, "message": message, "field": field}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(exc.code, exc.message, exc.field),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = first.get("loc", ())
        field = ".".join(str(p) for p in loc[1:]) or None
        return JSONResponse(
            status_code=422,
            content=envelope("VALIDATION_ERROR", first.get("msg", "Invalid request."), field),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        codes = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 429: "RATE_LIMITED"}
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(codes.get(exc.status_code, "INTERNAL"), str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Log the detail server-side; never leak internals to the browser.
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=envelope("INTERNAL", "Something went wrong. Please try again."),
        )
