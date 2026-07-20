import logging
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger("api_gateway.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        request.state.request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.correlation_id = request.headers.get("x-correlation-id") or request.state.request_id
        response = await call_next(request)
        response.headers.update(
            {
                "X-Request-ID": request.state.request_id,
                "X-Correlation-ID": request.state.correlation_id,
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            }
        )
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "request_id": request.state.request_id,
                "correlation_id": request.state.correlation_id,
            },
        )
        return response
