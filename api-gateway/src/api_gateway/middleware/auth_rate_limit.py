from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from api_gateway.core.config import Settings
from api_gateway.core.errors import GatewayError, error_response
from api_gateway.core.security import enforce_route_role, verify_access_token
from api_gateway.services.rate_limiter import RateLimiter

PUBLIC = {
    "/health",
    "/ready",
    "/version",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/signup",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    # LinkedIn redirects the browser here directly with no bearer token; the
    # callback authenticates the request itself via the opaque `state` value
    # instead (see social-publishing-service's linkedin_callback route).
    "/api/v1/publishing/linkedin/callback",
}


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Browser CORS preflight requests intentionally contain no bearer token.
        # CORSMiddleware validates the requested origin, method, and headers.
        if request.method == "OPTIONS":
            return await call_next(request)
        if request.url.path in {"/health", "/ready", "/version", "/docs", "/redoc", "/openapi.json"}:
            return await call_next(request)
        try:
            protected = (
                request.url.path.startswith("/api/v1/")
                and request.url.path not in PUBLIC
                and "/webhooks/" not in request.url.path
            )
            if protected:
                authorization = request.headers.get("authorization", "")
                if not authorization.startswith("Bearer "):
                    raise GatewayError(401, "AUTHENTICATION_REQUIRED", "A valid bearer token is required")
                request.state.claims = verify_access_token(authorization[7:], self.settings)
                if not await request.app.state.redis.exists(f"auth:session:{request.state.claims.jti}"):
                    raise GatewayError(401, "SESSION_REVOKED", "Access token session is no longer active")
                enforce_route_role(request.method, request.url.path, request.state.claims)
            identity = (
                f"account:{request.state.claims.account_id}"
                if protected
                else f"ip:{request.client.host if request.client else 'unknown'}"
            )
            limit = (
                self.settings.account_rate_limit
                if protected
                else (
                    self.settings.webhook_rate_limit
                    if "/webhooks/" in request.url.path
                    else self.settings.public_rate_limit
                )
            )
            limiter: RateLimiter = request.app.state.rate_limiter
            result = await limiter.check(
                identity, limit, self.settings.rate_limit_window_seconds, request.state.request_id
            )
            if not result.allowed:
                raise GatewayError(
                    429, "RATE_LIMIT_EXCEEDED", "Too many requests", {"retry_after": result.retry_after}
                )
            response = await call_next(request)
            response.headers.update(
                {
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": str(result.remaining),
                    "X-RateLimit-Reset": str(self.settings.rate_limit_window_seconds),
                }
            )
            return response
        except GatewayError as exc:
            response = error_response(request, exc.status_code, exc.code, exc.message, exc.details)
            if exc.status_code == 429:
                response.headers["Retry-After"] = str(exc.details.get("retry_after", 1))
            return response
