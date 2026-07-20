from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse


class AuthError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_response(
    request: Request, status_code: int, code: str, message: str, details: dict[str, Any] | None = None
) -> ORJSONResponse:
    return ORJSONResponse(
        {
            "success": False,
            "error": {"code": code, "message": message, "details": details or {}},
            "meta": {
                "requestId": getattr(request.state, "request_id", "unknown"),
                "correlationId": getattr(request.state, "correlation_id", "unknown"),
            },
        },
        status_code=status_code,
    )


async def auth_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if not isinstance(exc, AuthError):
        raise exc
    return error_response(request, exc.status_code, exc.code, exc.message, exc.details)


async def validation_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors = [
        {key: value for key, value in item.items() if key in {"type", "loc", "msg"}} for item in exc.errors()
    ]
    message = errors[0]["msg"] if errors else "Request validation failed"
    if isinstance(message, str):
        message = message.removeprefix("Value error, ")
    return error_response(
        request,
        422,
        "VALIDATION_ERROR",
        str(message),
        {"errors": errors},
    )
