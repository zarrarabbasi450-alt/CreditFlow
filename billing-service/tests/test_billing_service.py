from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from billing_service.core.config import Settings
from billing_service.models import Base, OutboxEvent, SubscriptionEvent
from billing_service.schemas.billing import CheckoutRequest, PlanChangeRequest, RefundRequest
from billing_service.services.billing import BillingService
from billing_service.services.outbox import OutboxPublisher
from conftest import ACCOUNT_ID, BusStub, StripeStub


@pytest.fixture
async def service() -> BillingService:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"billing": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        stripe_pro_price_id="price_pro",
        stripe_team_price_id="price_team",
        stripe_enterprise_price_id="price_enterprise",
        dunning_grace_days=7,
    )
    value = BillingService(sessions, StripeStub(), settings)
    value._test_engine = engine  # type: ignore[attr-defined]
    return value


async def test_account_checkout_plan_and_portal(service: BillingService) -> None:
    await service.create_account_customer({"account_id": str(ACCOUNT_ID), "name": "Acme"}, "c1")
    await service.create_account_customer({"account_id": str(ACCOUNT_ID), "name": "Acme"}, "duplicate")
    assert (await service.subscription(ACCOUNT_ID)).plan == "free"
    assert (await service.checkout(ACCOUNT_ID, CheckoutRequest(plan="pro", seats=2))).startswith("https://")
    assert (await service.checkout(ACCOUNT_ID, CheckoutRequest(plan="enterprise", seats=1))).startswith(
        "https://"
    )
    assert (await service.portal(ACCOUNT_ID)).startswith("https://")
    subscription = await service.subscription(ACCOUNT_ID)
    subscription.stripe_subscription_id = "sub_test"
    subscription.stripe_subscription_item_id = "si_test"
    async with service.sessions() as session, session.begin():
        await session.merge(subscription)
    updated = await service.change_plan(ACCOUNT_ID, PlanChangeRequest(plan="team", seats=4), "c2")
    assert updated.plan == "team" and updated.seats == 4
    free = await service.change_plan(ACCOUNT_ID, PlanChangeRequest(plan="free"), "c3")
    assert free.status == "canceling"


async def test_webhooks_refund_and_dunning(service: BillingService) -> None:
    await service.create_account_customer({"account_id": str(ACCOUNT_ID), "name": "Acme"}, "c1")
    failed = {
        "event_type": "billing.invoice.payment_failed",
        "correlation_id": "c",
        "payload": {
            "provider_event_id": "evt_failed",
            "event_type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "in_1",
                    "customer": f"cus_{str(ACCOUNT_ID)[:8]}",
                    "status": "open",
                    "currency": "usd",
                    "amount_due": 1000,
                    "amount_paid": 0,
                    "payment_intent": "pi_1",
                    "created": int(datetime.now(UTC).timestamp()),
                }
            },
        },
    }
    await service.handle_gateway_event(failed)
    await service.handle_gateway_event(failed)
    invoice = (await service.invoices(ACCOUNT_ID))[0]
    assert invoice.status == "open"
    refund = await service.refund(ACCOUNT_ID, RefundRequest(invoice_id=invoice.id, amount=500), "c2")
    assert refund.amount == 500
    paid = {
        **failed,
        "payload": {
            **failed["payload"],
            "provider_event_id": "evt_paid",
            "event_type": "invoice.paid",
            "data": {
                "object": {**failed["payload"]["data"]["object"], "status": "paid", "amount_paid": 1000}
            },
        },
    }
    await service.handle_gateway_event(paid)
    assert (await service.subscription(ACCOUNT_ID)).status == "active"
    subscription = await service.subscription(ACCOUNT_ID)
    subscription.status = "past_due"
    subscription.plan = "pro"
    subscription.stripe_subscription_id = "sub_test"
    subscription.grace_period_ends_at = datetime.now(UTC) - timedelta(minutes=1)
    async with service.sessions() as session, session.begin():
        await session.merge(subscription)
    assert await service.downgrade_overdue() == 1
    assert (await service.subscription(ACCOUNT_ID)).plan == "free"


async def test_missing_records(service: BillingService) -> None:
    assert (await service.subscription(uuid4())).plan == "free"
    with pytest.raises(Exception, match="not found"):
        await service.refund(ACCOUNT_ID, RefundRequest(invoice_id=uuid4()), "c")


async def test_subscription_cancellation_webhooks(service: BillingService) -> None:
    await service.create_account_customer({"account_id": str(ACCOUNT_ID), "name": "Acme"}, "c1")
    customer = f"cus_{str(ACCOUNT_ID)[:8]}"
    event = {
        "correlation_id": "cancel",
        "payload": {
            "provider_event_id": "evt_canceling",
            "event_type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test",
                    "customer": customer,
                    "status": "active",
                    "cancel_at_period_end": True,
                    "items": {
                        "data": [
                            {
                                "id": "si_test",
                                "current_period_end": int(
                                    (datetime.now(UTC) + timedelta(days=30)).timestamp()
                                ),
                                "price": {"id": "price_pro"},
                            }
                        ]
                    },
                }
            },
        },
    }
    await service.handle_gateway_event(event)
    canceling = await service.subscription(ACCOUNT_ID)
    assert canceling.status == "canceling"
    assert canceling.plan == "pro"
    assert canceling.current_period_end is not None

    event["payload"]["provider_event_id"] = "evt_canceled"
    event["payload"]["event_type"] = "customer.subscription.deleted"
    await service.handle_gateway_event(event)
    canceled = await service.subscription(ACCOUNT_ID)
    assert canceled.status == "canceled"
    assert canceled.plan == "free"


async def test_webhook_is_durable_before_processing(service: BillingService) -> None:
    event = {
        "correlation_id": "retry",
        "payload": {
            "provider_event_id": "evt_retry",
            "event_type": "unsupported.test",
            "data": {"object": {}},
        },
    }
    original = service._apply_webhook

    async def fail_once(*args: object) -> None:
        del args
        raise RuntimeError("processing failed")

    service._apply_webhook = fail_once  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="processing failed"):
        await service.handle_gateway_event(event)
    async with service.sessions() as session:
        stored = await session.scalar(
            select(SubscriptionEvent).where(SubscriptionEvent.provider_event_id == "evt_retry")
        )
        assert stored is not None and stored.processed is False

    service._apply_webhook = original  # type: ignore[method-assign]
    await service.handle_gateway_event(event)
    async with service.sessions() as session:
        stored = await session.scalar(
            select(SubscriptionEvent).where(SubscriptionEvent.provider_event_id == "evt_retry")
        )
        assert stored is not None and stored.processed is True


async def test_outbox_retries_without_marking_failed_publish(service: BillingService) -> None:
    await service.create_account_customer({"account_id": str(ACCOUNT_ID), "name": "Acme"}, "outbox")

    class FlakyBus(BusStub):
        async def publish(self, event: object) -> None:
            if not self.events:
                self.events.append("failed")
                raise ConnectionError("RabbitMQ unavailable")
            self.events.append(event)

    bus = FlakyBus()
    publisher = OutboxPublisher(service.sessions, bus, 0.01)
    with pytest.raises(ConnectionError, match="RabbitMQ unavailable"):
        await publisher.publish_batch()
    async with service.sessions() as session:
        stored = await session.scalar(select(OutboxEvent))
        assert stored is not None and stored.published_at is None

    assert await publisher.publish_batch() == 1
    async with service.sessions() as session:
        stored = await session.scalar(select(OutboxEvent))
        assert stored is not None and stored.published_at is not None and stored.attempts == 1
