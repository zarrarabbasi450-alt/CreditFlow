from typing import Any

from fastapi import Request
from fastapi.responses import ORJSONResponse


class CreditsError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


async def credits_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if not isinstance(exc, CreditsError):
        raise exc
    return ORJSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", ""),
                "correlation_id": getattr(request.state, "correlation_id", ""),
            },
        },
    )
