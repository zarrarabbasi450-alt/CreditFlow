from typing import Any

import httpx
from fastapi import Request, Response

from api_gateway.core.errors import GatewayError

HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}
TRUSTED = {
    "x-user-id",
    "x-account-id",
    "x-account-role",
    "x-platform-role",
    "x-request-id",
    "x-correlation-id",
}


class ProxyService:
    def __init__(self, client: httpx.AsyncClient, service_urls: dict[str, str]) -> None:
        self.client, self.service_urls = client, service_urls

    async def request_json(self, service: str, path: str, request: Request) -> Any:
        response = await self._send(service, path, request)
        if response.status_code >= 400:
            raise self._downstream_error(response)
        return response.json()

    async def service_healthy(self, service: str, timeout_seconds: float = 2.0) -> bool:
        if service not in self.service_urls:
            return False
        try:
            response = await self.client.get(
                f"{self.service_urls[service]}/health",
                timeout=timeout_seconds,
            )
            return response.status_code < 400
        except httpx.HTTPError:
            return False

    async def proxy(self, service: str, path: str, request: Request) -> Response:
        response = await self._send(service, path, request)
        if response.status_code >= 400:
            raise self._downstream_error(response)
        headers = {key: value for key, value in response.headers.items() if key.lower() not in HOP_HEADERS}
        return Response(
            response.content,
            status_code=response.status_code,
            headers=headers,
            media_type=response.headers.get("content-type"),
        )

    async def send(
        self, service: str, path: str, request: Request, body: bytes | None = None
    ) -> httpx.Response:
        """Like proxy(), but returns the raw downstream response for callers that need
        to inspect or rewrite the body/headers (e.g. moving a refresh token into a cookie)
        instead of passing it straight through to the browser."""
        response = await self._send(service, path, request, body_override=body)
        if response.status_code >= 400:
            raise self._downstream_error(response)
        return response

    async def _send(
        self, service: str, path: str, request: Request, body_override: bytes | None = None
    ) -> httpx.Response:
        if service not in self.service_urls:
            raise GatewayError(404, "ROUTE_NOT_FOUND", "No downstream service matches this route")
        headers = {
            key: value for key, value in request.headers.items() if key.lower() not in HOP_HEADERS | TRUSTED
        }
        claims = getattr(request.state, "claims", None)
        if claims:
            headers.update(
                {
                    "X-User-ID": claims.user_id,
                    "X-Account-ID": claims.account_id,
                    "X-Account-Role": claims.account_role,
                }
            )
            if claims.platform_role:
                headers["X-Platform-Role"] = claims.platform_role
        headers.update(
            {"X-Request-ID": request.state.request_id, "X-Correlation-ID": request.state.correlation_id}
        )
        try:
            if body_override is not None:
                body = body_override
            else:
                try:
                    body = await request.body()
                except RuntimeError as exc:
                    if str(exc) != "Receive channel has not been made available":
                        raise
                    body = b""
            return await self.client.request(
                request.method,
                f"{self.service_urls[service]}{path}",
                params=request.query_params,
                headers=headers,
                content=body,
            )
        except httpx.TimeoutException as exc:
            raise GatewayError(504, "DOWNSTREAM_TIMEOUT", f"The {service} service timed out") from exc
        except httpx.HTTPError as exc:
            raise GatewayError(
                503, "DOWNSTREAM_UNAVAILABLE", f"The {service} service is unavailable"
            ) from exc

    @staticmethod
    def _downstream_error(response: httpx.Response) -> GatewayError:
        try:
            body = response.json()
            error = body.get("error", body)
            return GatewayError(
                response.status_code,
                error.get("code", "DOWNSTREAM_ERROR"),
                error.get("message", "A downstream service rejected the request"),
                error.get("details", {}),
            )
        except ValueError:
            return GatewayError(
                response.status_code, "DOWNSTREAM_ERROR", "A downstream service rejected the request"
            )
