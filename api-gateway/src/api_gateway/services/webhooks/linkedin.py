from api_gateway.services.webhooks.hmac import verify_hmac


def verify_linkedin(body: bytes, signature: str | None, secret: str) -> None:
    verify_hmac(body, signature, secret, "LinkedIn")
