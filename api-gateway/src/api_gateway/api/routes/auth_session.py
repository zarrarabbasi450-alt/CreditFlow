import json
from contextlib import suppress

from fastapi import APIRouter, Request
from fastapi.responses import Response

from api_gateway.core.errors import GatewayError
from api_gateway.services.proxy import ProxyService

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

REFRESH_COOKIE = "creditflow_refresh_token"
COOKIE_PATH = "/api/v1/auth"


def _cookie_kwargs(request: Request) -> dict[str, object]:
    return {"httponly": True, "samesite": "lax", "secure": request.url.scheme == "https", "path": COOKIE_PATH}


def _split_tokens_response(request: Request, downstream_body: bytes, status_code: int) -> Response:
    """Auth-service returns {accessToken, refreshToken, expiresIn} to the gateway.
    The refresh token never reaches the browser as JSON — it's moved into an
    httpOnly cookie here so client-side JS (and XSS) cannot read or exfiltrate it."""
    payload = json.loads(downstream_body)
    tokens = payload.get("data", {}).get("tokens")
    refresh_token = tokens.pop("refreshToken", None) if tokens else None
    response = Response(json.dumps(payload).encode(), status_code=status_code, media_type="application/json")
    if refresh_token:
        response.set_cookie(REFRESH_COOKIE, refresh_token, **_cookie_kwargs(request))
    return response


@router.post("/login", operation_id="gateway_auth_login")
async def login(request: Request) -> Response:
    proxy: ProxyService = request.app.state.proxy
    downstream = await proxy.send("auth", "/api/v1/auth/login", request)
    return _split_tokens_response(request, downstream.content, downstream.status_code)


@router.post("/refresh", operation_id="gateway_auth_refresh")
async def refresh(request: Request) -> Response:
    proxy: ProxyService = request.app.state.proxy
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise GatewayError(401, "MISSING_REFRESH_TOKEN", "No active session was found")
    body = json.dumps({"refreshToken": refresh_token}).encode()
    downstream = await proxy.send("auth", "/api/v1/auth/refresh", request, body=body)
    return _split_tokens_response(request, downstream.content, downstream.status_code)


@router.post("/switch-account", operation_id="gateway_auth_switch_account")
async def switch_account(request: Request) -> Response:
    proxy: ProxyService = request.app.state.proxy
    downstream = await proxy.send("auth", "/api/v1/auth/switch-account", request)
    return _split_tokens_response(request, downstream.content, downstream.status_code)


@router.post("/logout", operation_id="gateway_auth_logout")
async def logout(request: Request) -> Response:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        proxy: ProxyService = request.app.state.proxy
        body = json.dumps({"refreshToken": refresh_token}).encode()
        # A stale/expired refresh cookie means the server-side session is already
        # gone (or on its way out) — either way the browser's cookie still needs
        # clearing, so a downstream rejection here shouldn't block that.
        with suppress(GatewayError):
            await proxy.send("auth", "/api/v1/auth/logout", request, body=body)
    response = Response(
        json.dumps({"success": True, "data": {"message": "Logged out successfully"}}).encode(),
        status_code=200,
        media_type="application/json",
    )
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    return response
