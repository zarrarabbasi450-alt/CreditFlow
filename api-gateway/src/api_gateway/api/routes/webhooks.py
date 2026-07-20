import json
from typing import Any

from fastapi import APIRouter, Request

from api_gateway.core.config import Settings
from api_gateway.core.errors import GatewayError
from api_gateway.schemas.events import EventEnvelope
from api_gateway.services.webhooks.linkedin import verify_linkedin
from api_gateway.services.webhooks.openrouter import verify_openrouter
from api_gateway.services.webhooks.stripe import verify_stripe

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


async def process(provider: str, request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    body = await request.body()
    if len(body) > settings.webhook_max_body_bytes:
        raise GatewayError(413, "PAYLOAD_TOO_LARGE", "Webhook payload is too large")
    if provider == "stripe":
        payload = verify_stripe(body, request.headers.get("stripe-signature"), settings.stripe_webhook_secret)
    else:
        signature = request.headers.get("x-webhook-signature")
        (verify_linkedin if provider == "linkedin" else verify_openrouter)(
            body,
            signature,
            settings.linkedin_webhook_secret
            if provider == "linkedin"
            else settings.openrouter_webhook_secret,
        )
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise GatewayError(400, "INVALID_WEBHOOK_PAYLOAD", "Webhook payload must be valid JSON") from exc
    event_id = str(payload.get("id") or payload.get("event_id") or "")
    if not event_id:
        raise GatewayError(400, "MISSING_EVENT_ID", "Webhook event ID is required")
    if not await request.app.state.redis.deduplicate(f"webhook:{provider}:{event_id}"):
        return {"success": True, "duplicate": True, "event_id": event_id}
    provider_type = str(payload.get("type", "received"))
    prefix = {"stripe": "billing", "linkedin": "social", "openrouter": "ai"}[provider]
    event = EventEnvelope(
        event_type=f"{prefix}.{provider_type}",
        correlation_id=request.state.correlation_id,
        payload={
            "provider": provider,
            "provider_event_id": event_id,
            "event_type": provider_type,
            "data": payload.get("data", {}),
        },
    )
    try:
        await request.app.state.rabbitmq.publish(event)
    except Exception:
        # A failed publish must remain retryable by the provider.
        await request.app.state.redis.delete(f"webhook:{provider}:{event_id}")
        raise
    return {"success": True, "duplicate": False, "event_id": event_id}


@router.post("/stripe")
async def stripe_hook(request: Request) -> dict[str, Any]:
    return await process("stripe", request)


@router.post("/linkedin")
async def linkedin_hook(request: Request) -> dict[str, Any]:
    return await process("linkedin", request)


@router.post("/openrouter")
async def openrouter_hook(request: Request) -> dict[str, Any]:
    return await process("openrouter", request)
