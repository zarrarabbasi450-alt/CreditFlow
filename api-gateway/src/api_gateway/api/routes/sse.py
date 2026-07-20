from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from api_gateway.core.errors import GatewayError

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/generations/{generation_id}/stream")
async def stream(generation_id: str, request: Request) -> StreamingResponse:
    claims = request.state.claims
    ownership: Any = await request.app.state.proxy.request_json(
        "ai", f"/internal/generations/{generation_id}/ownership", request
    )
    if ownership.get("account_id") != claims.account_id:
        raise GatewayError(403, "GENERATION_ACCESS_DENIED", "Generation does not belong to this account")
    return StreamingResponse(
        request.app.state.sse.stream(request, claims.account_id, generation_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
