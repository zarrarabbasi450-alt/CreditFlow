from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse


class GatewayError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self.status_code, self.code, self.message = status_code, code, message
        self.details = details or {}


def error_response(
    request: Request, status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=status,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "request_id": getattr(request.state, "request_id", "unknown"),
                "correlation_id": getattr(request.state, "correlation_id", "unknown"),
            },
        },
    )


async def gateway_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if not isinstance(exc, GatewayError):
        raise exc
    return error_response(request, exc.status_code, exc.code, exc.message, exc.details)


async def validation_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    return error_response(
        request, 422, "VALIDATION_ERROR", "Request validation failed", {"errors": exc.errors()}
    )


async def unexpected_error_handler(request: Request, _exc: Exception) -> ORJSONResponse:
    return error_response(request, 500, "INTERNAL_ERROR", "An unexpected error occurred")
