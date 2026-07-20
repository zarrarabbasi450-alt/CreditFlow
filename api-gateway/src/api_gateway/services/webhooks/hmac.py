import hashlib
import hmac

from api_gateway.core.errors import GatewayError


def verify_hmac(body: bytes, signature: str | None, secret: str, provider: str) -> None:
    if not signature or not secret:
        raise GatewayError(401, "INVALID_WEBHOOK_SIGNATURE", f"Invalid {provider} webhook signature")
    supplied = signature.removeprefix("sha256=")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise GatewayError(401, "INVALID_WEBHOOK_SIGNATURE", f"Invalid {provider} webhook signature")
