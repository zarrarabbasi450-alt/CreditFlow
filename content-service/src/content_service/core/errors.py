from typing import Any

from fastapi import Request
from fastapi.responses import ORJSONResponse


class ContentError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


async def content_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    error = exc if isinstance(exc, ContentError) else ContentError(500, "INTERNAL_ERROR", "Internal error")
    request_id = getattr(request.state, "request_id", "")
    correlation_id = getattr(request.state, "correlation_id", request_id)
    return ORJSONResponse(
        status_code=error.status_code,
        content={
            "success": False,
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
                "request_id": request_id,
                "correlation_id": correlation_id,
            },
        },
    )
