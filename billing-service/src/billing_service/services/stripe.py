from typing import Any, Protocol, cast

import stripe

from billing_service.core.config import Settings
from billing_service.core.errors import BillingError


class StripeProtocol(Protocol):
    def create_customer(self, account_id: str, name: str) -> str: ...
    def create_checkout(self, customer: str, price: str, seats: int, account_id: str) -> str: ...
    def create_credit_checkout(
        self, customer: str, credits: int, unit_amount_cents: int, account_id: str
    ) -> str: ...
    def create_portal(self, customer: str) -> str: ...
    def update_subscription(
        self, subscription_id: str, item_id: str, price: str, seats: int, proration: str
    ) -> dict[str, Any]: ...
    def cancel_subscription(self, subscription_id: str) -> dict[str, Any]: ...
    def create_refund(self, payment_intent: str, amount: int | None, reason: str) -> dict[str, Any]: ...
    def create_escrow(
        self, customer: str, buyer_account_id: str, seller_account_id: str, listing_id: str, amount: int
    ) -> dict[str, Any]: ...
    def capture_escrow(self, payment_intent_id: str) -> dict[str, Any]: ...


class StripeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        stripe.api_key = settings.stripe_secret_key

    @staticmethod
    def _call(function: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return cast(dict[str, Any], dict(function(*args, **kwargs)))
        except stripe.StripeError as exc:
            raise BillingError(
                502, "STRIPE_ERROR", str(exc.user_message or "Stripe rejected the request")
            ) from exc

    def create_customer(self, account_id: str, name: str) -> str:
        result = self._call(
            stripe.Customer.create,
            name=name,
            metadata={"account_id": account_id},
            idempotency_key=f"account-{account_id}",
        )
        return str(result["id"])

    def create_checkout(self, customer: str, price: str, seats: int, account_id: str) -> str:
        result = self._call(
            stripe.checkout.Session.create,
            mode="subscription",
            customer=customer,
            line_items=[{"price": price, "quantity": seats}],
            success_url=self.settings.stripe_checkout_success_url,
            cancel_url=self.settings.stripe_checkout_cancel_url,
            client_reference_id=account_id,
            subscription_data={"metadata": {"account_id": account_id}},
        )
        return str(result["url"])

    def create_credit_checkout(
        self, customer: str, credits: int, unit_amount_cents: int, account_id: str
    ) -> str:
        # price_data is built inline instead of referencing a pre-created Stripe Price ID,
        # since the credit amount (and therefore the charge) is chosen per purchase.
        metadata = {"purpose": "credit_purchase", "account_id": account_id, "credits": str(credits)}
        result = self._call(
            stripe.checkout.Session.create,
            mode="payment",
            customer=customer,
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"{credits:,} CreditFlow credits"},
                        "unit_amount": unit_amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=self.settings.stripe_credit_checkout_success_url,
            cancel_url=self.settings.stripe_credit_checkout_cancel_url,
            client_reference_id=account_id,
            metadata=metadata,
            payment_intent_data={"metadata": metadata},
            idempotency_key=f"credit-purchase-{account_id}-{credits}-{unit_amount_cents}",
        )
        return str(result["url"])

    def create_portal(self, customer: str) -> str:
        result = self._call(
            stripe.billing_portal.Session.create,
            customer=customer,
            return_url=self.settings.stripe_portal_return_url,
        )
        return str(result["url"])

    def update_subscription(
        self, subscription_id: str, item_id: str, price: str, seats: int, proration: str
    ) -> dict[str, Any]:
        return self._call(
            stripe.Subscription.modify,
            subscription_id,
            items=[{"id": item_id, "price": price, "quantity": seats}],
            proration_behavior=proration,
            payment_behavior="pending_if_incomplete" if proration == "always_invoice" else "allow_incomplete",
            # Picking a plan is an explicit "keep this subscription" signal — it
            # should also undo a pending cancel_at_period_end from an earlier
            # downgrade-to-free, not just change the price while still letting it lapse.
            cancel_at_period_end=False,
        )

    def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        return self._call(stripe.Subscription.modify, subscription_id, cancel_at_period_end=True)

    def create_refund(self, payment_intent: str, amount: int | None, reason: str) -> dict[str, Any]:
        values: dict[str, Any] = {"payment_intent": payment_intent, "reason": reason}
        if amount is not None:
            values["amount"] = amount
        return self._call(stripe.Refund.create, **values)

    def create_escrow(
        self, customer: str, buyer_account_id: str, seller_account_id: str, listing_id: str, amount: int
    ) -> dict[str, Any]:
        return self._call(
            stripe.PaymentIntent.create,
            amount=amount,
            currency="usd",
            customer=customer,
            capture_method="manual",
            automatic_payment_methods={"enabled": True},
            metadata={
                "purpose": "credits_marketplace",
                "buyer_account_id": buyer_account_id,
                "seller_account_id": seller_account_id,
                "listing_id": listing_id,
            },
            idempotency_key=f"credits-listing-{listing_id}-{buyer_account_id}",
        )

    def capture_escrow(self, payment_intent_id: str) -> dict[str, Any]:
        return self._call(stripe.PaymentIntent.capture, payment_intent_id)
