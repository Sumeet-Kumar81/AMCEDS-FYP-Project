"""Contract C-4 error format: every error response body is ``{code, message, details}``.

Registered in ``app.main``. Validation errors (422) list each problem's location, message and type,
but never echo the submitted value, so a password or phone number cannot leak into a response.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

ERROR_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "too_many_requests",
    501: "not_implemented",
    503: "service_unavailable",
}


class ErrorBody(BaseModel):
    """The body of every error response (C-4)."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: Any = None


class ApiError(Exception):
    """Raise to return a contract error with an explicit code and details."""

    def __init__(self, status_code: int, message: str, *, code: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code or ERROR_CODES.get(status_code, f"http_{status_code}")
        self.message = message
        self.details = details


class NotImplementedYet(ApiError):
    """501 for an endpoint that is in the contract but not built yet. Never returns fake data."""

    def __init__(self, task_id: str) -> None:
        super().__init__(
            501,
            f"This endpoint is in the API contract but is not implemented yet (task {task_id}).",
            details={"task": task_id},
        )


def _body(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=ErrorBody(code=code, message=message, details=details).model_dump())


async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    return _body(exc.status_code, exc.code, exc.message, exc.details)


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = ERROR_CODES.get(exc.status_code, f"http_{exc.status_code}")
    message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ")
    response = _body(exc.status_code, code, message)
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    problems = [
        {"loc": list(err.get("loc", ())), "msg": str(err.get("msg", "")), "type": str(err.get("type", ""))}
        for err in exc.errors()
    ]
    return _body(422, "validation_error", "The request is not valid.", problems)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error)  # type: ignore[arg-type]


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    501: {"model": ErrorBody, "description": "In the contract but not implemented yet"},
    422: {"model": ErrorBody, "description": "Validation error"},
}
"""Attach to stub routers so OpenAPI documents the contract error body."""
