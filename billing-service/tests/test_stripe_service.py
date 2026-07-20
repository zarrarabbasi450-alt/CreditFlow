from typing import Any

import stripe

from billing_service.core.config import Settings
from billing_service.services.stripe import StripeService


def test_checkout_uses_stripe_dynamic_payment_methods(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def create(**kwargs: Any) -> dict[str, str]:
        captured.update(kwargs)
        return {"id": "cs_test", "url": "https://checkout.stripe.test/session"}

    monkeypatch.setattr(stripe.checkout.Session, "create", create)
    service = StripeService(Settings(stripe_secret_key="sk_test_example"))  # noqa: S106
    url = service.create_checkout("cus_test", "price_test", 2, "account-test")

    assert url == "https://checkout.stripe.test/session"
    assert "automatic_payment_methods" not in captured
    assert "payment_method_types" not in captured
    assert captured["mode"] == "subscription"
