from collections.abc import Callable
from typing import Any, cast

import stripe

from api_gateway.core.errors import GatewayError


def verify_stripe(body: bytes, signature: str | None, secret: str) -> dict[str, Any]:
    try:
        construct_event = cast(Callable[[bytes, str, str], dict[str, Any]], stripe.Webhook.construct_event)
        event = construct_event(body, signature or "", secret)
        return dict(event)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise GatewayError(401, "INVALID_WEBHOOK_SIGNATURE", "Invalid Stripe webhook signature") from exc
