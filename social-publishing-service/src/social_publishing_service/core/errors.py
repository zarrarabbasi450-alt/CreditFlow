from typing import Any

from fastapi import Request
from fastapi.responses import ORJSONResponse


class SocialPublishingError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


async def social_error_handler(request: Request, exc: SocialPublishingError) -> ORJSONResponse:
    return ORJSONResponse(
        {
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None),
                "correlation_id": getattr(request.state, "correlation_id", None),
            },
        },
        status_code=exc.status_code,
    )
