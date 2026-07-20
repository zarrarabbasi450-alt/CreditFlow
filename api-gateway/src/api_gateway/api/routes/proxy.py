from fastapi import APIRouter, Request
from fastapi.responses import Response

from api_gateway.services.proxy import ProxyService

router = APIRouter(prefix="/api/v1")
ALIASES = {
    "auth": "auth",
    "users": "users",
    "tenants": "users",
    "accounts": "users",
    "invites": "users",
    "billing": "billing",
    "credits": "credits",
    "marketplace": "credits",
    "usage": "usage",
    "ai": "ai",
    "content": "content",
    "scheduler": "scheduler",
    "publishing": "publishing",
    "scraper": "scraper",
    "notifications": "notifications",
    "admin": "admin",
}


async def route(path: str, request: Request) -> Response:
    segment = path.split("/", 1)[0]
    service = ALIASES.get(segment, segment)
    proxy: ProxyService = request.app.state.proxy
    return await proxy.proxy(service, f"/api/v1/{path}", request)


@router.get("/{path:path}", operation_id="proxy_get")
async def route_get(path: str, request: Request) -> Response:
    return await route(path, request)


@router.post("/{path:path}", operation_id="proxy_post")
async def route_post(path: str, request: Request) -> Response:
    return await route(path, request)


@router.put("/{path:path}", operation_id="proxy_put")
async def route_put(path: str, request: Request) -> Response:
    return await route(path, request)


@router.patch("/{path:path}", operation_id="proxy_patch")
async def route_patch(path: str, request: Request) -> Response:
    return await route(path, request)


@router.delete("/{path:path}", operation_id="proxy_delete")
async def route_delete(path: str, request: Request) -> Response:
    return await route(path, request)


@router.options("/{path:path}", operation_id="proxy_options")
async def route_options(path: str, request: Request) -> Response:
    return await route(path, request)
