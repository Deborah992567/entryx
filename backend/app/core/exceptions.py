"""Typed application exceptions and the FastAPI error envelope.

Every API error returns the uniform shape:
    {"detail": {"code": "ERR_CODE", "message": "...", "fields": {...}}}
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class EntryXError(Exception):
    code = "ERR_ENTRYX"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str, *, fields: dict[str, Any] | None = None) -> None:
        self.message = message
        self.fields = fields or {}


class NotFoundError(EntryXError):
    code = "ERR_NOT_FOUND"
    http_status = status.HTTP_404_NOT_FOUND


class ConflictError(EntryXError):
    code = "ERR_CONFLICT"
    http_status = status.HTTP_409_CONFLICT


class UnauthorizedError(EntryXError):
    code = "ERR_UNAUTHORIZED"
    http_status = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(EntryXError):
    code = "ERR_FORBIDDEN"
    http_status = status.HTTP_403_FORBIDDEN


class ValidationError(EntryXError):
    code = "ERR_VALIDATION"
    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT


class RateLimitError(EntryXError):
    code = "ERR_RATE_LIMITED"
    http_status = status.HTTP_429_TOO_MANY_REQUESTS


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(EntryXError)
    async def _entryx_error(_: Request, exc: EntryXError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"detail": {"code": exc.code, "message": exc.message, "fields": exc.fields}},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, Any] = {}
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
            fields[loc] = err.get("msg")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": {
                    "code": "ERR_VALIDATION",
                    "message": "Request validation failed",
                    "fields": fields,
                }
            },
        )
