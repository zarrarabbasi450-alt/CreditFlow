from typing import Any

from fastapi import Request
from fastapi.responses import ORJSONResponse


class BillingError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self.status_code, self.code, self.message = status_code, code, message
        self.details = details or {}


async def billing_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    del request
    if not isinstance(exc, BillingError):
        raise exc
    return ORJSONResponse(
        {"success": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        status_code=exc.status_code,
    )
