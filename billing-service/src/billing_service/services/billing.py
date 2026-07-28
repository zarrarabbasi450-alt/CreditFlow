from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from billing_service.core.config import Settings
from billing_service.core.errors import BillingError
from billing_service.models import Invoice, OutboxEvent, Plan, Refund, Subscription, SubscriptionEvent
from billing_service.schemas.billing import (
    CheckoutRequest,
    CreditCheckoutRequest,
    EscrowCreateRequest,
    PlanChangeRequest,
    RefundRequest,
)
from billing_service.services.stripe import StripeProtocol


class BillingService:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], stripe_service: StripeProtocol, settings: Settings
    ) -> None:
        self.sessions, self.stripe, self.settings = sessions, stripe_service, settings

    async def create_account_customer(self, payload: dict[str, Any], correlation_id: str) -> None:
        account_id = UUID(str(payload["account_id"]))
        async with self.sessions() as session:
            if await session.scalar(select(Subscription).where(Subscription.account_id == account_id)):
                return
        customer_id = self.stripe.create_customer(
            str(account_id), str(payload.get("name", "CreditFlow account"))
        )
        try:
            async with self.sessions() as session, session.begin():
                session.add(Subscription(account_id=account_id, stripe_customer_id=customer_id))
                session.add(
                    self._outbox(
                        "subscription.updated",
                        str(account_id),
                        {"account_id": str(account_id), "plan": "free", "status": "active"},
                        correlation_id,
                    )
                )
        except IntegrityError:
            return

    async def subscription(self, account_id: UUID) -> Subscription:
        async with self.sessions() as session:
            value: Subscription | None = await session.scalar(
                select(Subscription).where(Subscription.account_id == account_id)
            )
            if value is not None:
                return value
        # Backfills accounts created before the durable Billing queue existed.
        await self.create_account_customer(
            {"account_id": str(account_id), "name": "CreditFlow account"}, "billing-backfill"
        )
        async with self.sessions() as session:
            value = await session.scalar(select(Subscription).where(Subscription.account_id == account_id))
            if value is None:
                raise BillingError(
                    503, "BILLING_PROVISIONING_FAILED", "Billing account could not be provisioned"
                )
            return value

    async def invoices(self, account_id: UUID) -> list[Invoice]:
        async with self.sessions() as session:
            values = await session.scalars(
                select(Invoice).where(Invoice.account_id == account_id).order_by(Invoice.issued_at.desc())
            )
            return list(values.all())

    async def checkout(self, account_id: UUID, payload: CheckoutRequest) -> str:
        subscription = await self.subscription(account_id)
        if subscription.stripe_subscription_id and subscription.status not in {"canceled", "downgraded"}:
            # Starting a fresh Checkout Session here would create a second, unrelated
            # Stripe subscription instead of changing the existing one — leaving the
            # old one still billing in the background. Plan changes on an existing
            # subscription must go through change_plan()/PATCH /billing/subscription.
            raise BillingError(
                409,
                "SUBSCRIPTION_ALREADY_ACTIVE",
                "An active subscription already exists — change your plan instead of starting a new checkout",
            )
        price = self._price(payload.plan)
        return self.stripe.create_checkout(
            subscription.stripe_customer_id, price, payload.seats, str(account_id)
        )

    async def credit_checkout(self, account_id: UUID, payload: CreditCheckoutRequest) -> str:
        subscription = await self.subscription(account_id)
        unit_amount_cents = payload.credits * self.settings.credit_price_cents
        return self.stripe.create_credit_checkout(
            subscription.stripe_customer_id, payload.credits, unit_amount_cents, str(account_id)
        )

    async def portal(self, account_id: UUID) -> str:
        return self.stripe.create_portal((await self.subscription(account_id)).stripe_customer_id)

    async def create_escrow(self, account_id: UUID, payload: EscrowCreateRequest) -> dict[str, Any]:
        subscription = await self.subscription(account_id)
        return self.stripe.create_escrow(
            subscription.stripe_customer_id,
            str(account_id),
            str(payload.seller_account_id),
            str(payload.listing_id),
            payload.amount,
        )

    async def capture_escrow(self, account_id: UUID, payment_intent_id: str) -> dict[str, Any]:
        result = self.stripe.capture_escrow(payment_intent_id)
        metadata = dict(result.get("metadata") or {})
        if metadata.get("buyer_account_id") != str(account_id):
            raise BillingError(403, "ESCROW_ACCESS_DENIED", "Payment intent belongs to another account")
        return result

    async def change_plan(
        self, account_id: UUID, payload: PlanChangeRequest, correlation_id: str
    ) -> Subscription:
        subscription = await self.subscription(account_id)
        if payload.plan == Plan.FREE:
            if subscription.stripe_subscription_id:
                self.stripe.cancel_subscription(subscription.stripe_subscription_id)
            subscription.status = "canceling"
        else:
            if not subscription.stripe_subscription_id or not subscription.stripe_subscription_item_id:
                raise BillingError(
                    409, "CHECKOUT_REQUIRED", "Start a paid subscription through Checkout first"
                )
            self.stripe.update_subscription(
                subscription.stripe_subscription_id,
                subscription.stripe_subscription_item_id,
                self._price(payload.plan),
                payload.seats,
                payload.proration_behavior,
            )
            subscription.plan, subscription.seats, subscription.status = (
                payload.plan,
                payload.seats,
                "active",
            )
        async with self.sessions() as session, session.begin():
            merged = await session.merge(subscription)
            session.add(
                self._outbox(
                    "subscription.updated",
                    str(account_id),
                    {
                        "account_id": str(account_id),
                        "plan": str(merged.plan),
                        "status": merged.status,
                        "seats": merged.seats,
                    },
                    correlation_id,
                )
            )
        return subscription

    async def refund(self, account_id: UUID, payload: RefundRequest, correlation_id: str) -> Refund:
        async with self.sessions() as session:
            invoice = await session.get(Invoice, payload.invoice_id)
            if invoice is None or invoice.account_id != account_id:
                raise BillingError(404, "INVOICE_NOT_FOUND", "Invoice was not found")
            if not invoice.payment_intent_id:
                raise BillingError(409, "INVOICE_NOT_REFUNDABLE", "Invoice has no refundable payment")
        result = self.stripe.create_refund(invoice.payment_intent_id, payload.amount, payload.reason)
        refund = Refund(
            account_id=account_id,
            invoice_id=invoice.id,
            stripe_refund_id=str(result["id"]),
            amount=int(result["amount"]),
            currency=str(result["currency"]),
            reason=payload.reason,
            status=str(result["status"]),
        )
        async with self.sessions() as session, session.begin():
            session.add(refund)
            session.add(
                self._outbox(
                    "refund.issued",
                    str(refund.id),
                    {
                        "account_id": str(account_id),
                        "invoice_id": str(invoice.id),
                        "refund_id": str(refund.id),
                        "amount": refund.amount,
                        "currency": refund.currency,
                    },
                    correlation_id,
                )
            )
        return refund

    async def handle_gateway_event(self, envelope: dict[str, Any]) -> None:
        payload = dict(envelope.get("payload", {}))
        provider_event_id = str(payload.get("provider_event_id", ""))
        event_type = str(payload.get("event_type", ""))
        data_wrapper = payload.get("data", {})
        data = dict(data_wrapper.get("object", data_wrapper)) if isinstance(data_wrapper, dict) else {}
        correlation_id = str(envelope.get("correlation_id", provider_event_id))
        # Commit the inbox record first. If business processing fails, RabbitMQ can
        # redeliver the message and resume from the durable, unprocessed event.
        try:
            async with self.sessions() as session, session.begin():
                if not await session.scalar(
                    select(SubscriptionEvent).where(SubscriptionEvent.provider_event_id == provider_event_id)
                ):
                    session.add(
                        SubscriptionEvent(
                            provider_event_id=provider_event_id,
                            event_type=event_type,
                            payload=payload,
                        )
                    )
        except IntegrityError:
            # A concurrent delivery may win the unique provider-event insert.
            pass

        async with self.sessions() as session, session.begin():
            stored = await session.scalar(
                select(SubscriptionEvent)
                .where(SubscriptionEvent.provider_event_id == provider_event_id)
                .with_for_update()
            )
            if stored is None or stored.processed:
                return
            await self._apply_webhook(session, event_type, data, correlation_id)
            stored.processed = True

    async def _apply_webhook(
        self, session: AsyncSession, event_type: str, data: dict[str, Any], correlation_id: str
    ) -> None:
        metadata = dict(data.get("metadata") or {})
        customer_id = str(data.get("customer") or "")
        subscription = await session.scalar(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        )
        if subscription is None and metadata.get("account_id"):
            subscription = await session.scalar(
                select(Subscription).where(Subscription.account_id == UUID(str(metadata["account_id"])))
            )
        if event_type.startswith("invoice.") and subscription is not None:
            invoice = await session.scalar(
                select(Invoice).where(Invoice.stripe_invoice_id == str(data["id"]))
            )
            if invoice is None:
                invoice = Invoice(
                    account_id=subscription.account_id,
                    stripe_invoice_id=str(data["id"]),
                    number=data.get("number"),
                    status=str(data.get("status", "open")),
                    currency=str(data.get("currency", "usd")),
                    amount_due=int(data.get("amount_due", 0)),
                    amount_paid=int(data.get("amount_paid", 0)),
                    payment_intent_id=self._id(data.get("payment_intent")),
                    hosted_invoice_url=data.get("hosted_invoice_url"),
                    invoice_pdf=data.get("invoice_pdf"),
                    issued_at=datetime.fromtimestamp(
                        int(data.get("created", datetime.now(UTC).timestamp())), UTC
                    ),
                )
                session.add(invoice)
            else:
                invoice.status, invoice.amount_paid = (
                    str(data.get("status", invoice.status)),
                    int(data.get("amount_paid", invoice.amount_paid)),
                )
            if event_type == "invoice.paid":
                subscription.status, subscription.grace_period_ends_at = "active", None
                invoice_plan = self._invoice_plan(data, Plan(subscription.plan))
                session.add(
                    self._outbox(
                        "invoice.paid",
                        str(invoice.id),
                        {
                            "account_id": str(subscription.account_id),
                            "invoice_id": str(invoice.id),
                            "plan": str(invoice_plan),
                            "amount": invoice.amount_paid,
                            "currency": invoice.currency,
                        },
                        correlation_id,
                    )
                )
            elif event_type == "invoice.payment_failed":
                subscription.status = "past_due"
                subscription.grace_period_ends_at = datetime.now(UTC) + timedelta(
                    days=self.settings.dunning_grace_days
                )
                session.add(
                    self._outbox(
                        "payment.failed",
                        str(invoice.id),
                        {
                            "account_id": str(subscription.account_id),
                            "invoice_id": str(invoice.id),
                            "grace_period_ends_at": subscription.grace_period_ends_at.isoformat(),
                        },
                        correlation_id,
                    )
                )
        elif event_type.startswith("customer.subscription.") and subscription is not None:
            items = list(dict(data.get("items") or {}).get("data") or [])
            subscription.stripe_subscription_id = str(data["id"])
            subscription.stripe_subscription_item_id = str(items[0]["id"]) if items else None
            stripe_status = str(data.get("status", subscription.status))
            if event_type == "customer.subscription.deleted":
                subscription.plan, subscription.status = Plan.FREE, "canceled"
                subscription.stripe_subscription_item_id = None
            elif data.get("cancel_at_period_end"):
                subscription.status = "canceling"
            else:
                subscription.status = stripe_status
            item_period_end = items[0].get("current_period_end") if items else None
            period_end = data.get("current_period_end") or item_period_end
            subscription.current_period_end = (
                datetime.fromtimestamp(int(period_end), UTC) if period_end else None
            )
            price_id = str(dict(items[0].get("price") or {}).get("id", "")) if items else ""
            if event_type != "customer.subscription.deleted":
                subscription.plan = next(
                    (plan for plan, configured in self.settings.price_ids.items() if configured == price_id),
                    subscription.plan,
                )
            session.add(
                self._outbox(
                    "subscription.updated",
                    str(subscription.account_id),
                    {
                        "account_id": str(subscription.account_id),
                        "plan": subscription.plan,
                        "status": subscription.status,
                    },
                    correlation_id,
                )
            )
        elif event_type == "checkout.session.completed" and metadata.get("purpose") == "credit_purchase":
            credit_account_id = str(metadata.get("account_id", ""))
            credits = int(metadata.get("credits", 0))
            if credit_account_id and credits > 0:
                session.add(
                    self._outbox(
                        "credits.purchased",
                        str(data.get("id")),
                        {
                            "account_id": credit_account_id,
                            "credits": credits,
                            "payment_intent_id": self._id(data.get("payment_intent")),
                            "amount": int(data.get("amount_total", 0)),
                            "currency": str(data.get("currency", "usd")),
                        },
                        correlation_id,
                    )
                )

    async def downgrade_overdue(self) -> int:
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            values = await session.scalars(
                select(Subscription)
                .where(Subscription.status == "past_due", Subscription.grace_period_ends_at <= now)
                .with_for_update(skip_locked=True)
            )
            subscriptions = list(values.all())
            for subscription in subscriptions:
                if subscription.stripe_subscription_id:
                    self.stripe.cancel_subscription(subscription.stripe_subscription_id)
                subscription.plan, subscription.status, subscription.grace_period_ends_at = (
                    Plan.FREE,
                    "downgraded",
                    None,
                )
                session.add(
                    self._outbox(
                        "subscription.downgraded",
                        str(subscription.account_id),
                        {
                            "account_id": str(subscription.account_id),
                            "plan": "free",
                            "reason": "payment_failed",
                        },
                        "dunning-poller",
                    )
                )
            return len(subscriptions)

    def _price(self, plan: str) -> str:
        value = self.settings.price_ids.get(str(plan), "")
        if not value or value.endswith("CHANGE_ME"):
            raise BillingError(503, "PLAN_NOT_CONFIGURED", f"Stripe price for {plan} is not configured")
        return value

    def _invoice_plan(self, data: dict[str, Any], fallback: Plan) -> Plan:
        """Resolve the purchased plan from invoice lines, independent of webhook ordering."""
        lines = list(dict(data.get("lines") or {}).get("data") or [])
        for line in lines:
            if not isinstance(line, dict):
                continue
            pricing = dict(line.get("pricing") or {})
            price_details = dict(pricing.get("price_details") or {})
            price = line.get("price")
            price_id = str(
                price_details.get("price") or (price.get("id") if isinstance(price, dict) else price) or ""
            )
            matched = next(
                (plan for plan, configured in self.settings.price_ids.items() if configured == price_id),
                None,
            )
            if matched is not None:
                return Plan(matched)
        return fallback

    @staticmethod
    def _id(value: Any) -> str | None:
        return str(value.get("id")) if isinstance(value, dict) else (str(value) if value else None)

    @staticmethod
    def _outbox(
        event_type: str, aggregate_id: str, payload: dict[str, Any], correlation_id: str
    ) -> OutboxEvent:
        return OutboxEvent(
            event_type=event_type, aggregate_id=aggregate_id, payload=payload, correlation_id=correlation_id
        )
