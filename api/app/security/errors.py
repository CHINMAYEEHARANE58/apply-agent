from typing import Any

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=payload)


async def http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        return error_response(500, "internal_error", "An unexpected error occurred.")
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", "request_error"))
        message = str(exc.detail.get("message", "Request failed."))
        return error_response(exc.status_code, code, message, exc.detail.get("details"))
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return error_response(exc.status_code, "request_error", message)


async def validation_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return error_response(500, "internal_error", "An unexpected error occurred.")
    return error_response(422, "validation_error", "Request validation failed.", jsonable_encoder(exc.errors()))


def not_found(entity: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{entity} was not found.")
