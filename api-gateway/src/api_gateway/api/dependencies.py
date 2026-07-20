from typing import cast

from fastapi import Request

from api_gateway.core.security import TokenClaims
from api_gateway.services.proxy import ProxyService


def claims(request: Request) -> TokenClaims:
    return cast(TokenClaims, request.state.claims)


def proxy(request: Request) -> ProxyService:
    return cast(ProxyService, request.app.state.proxy)
