from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from credits_service.core.config import Settings
from credits_service.core.errors import CreditsError
from credits_service.models import CreditLedger, LedgerType, ListingStatus, MarketplaceListing, ProcessedEvent
from credits_service.schemas.credits import ListingCreate
from credits_service.schemas.events import EventEnvelope
from credits_service.services.rabbitmq import EventBusProtocol


class CreditsService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        events: EventBusProtocol,
        settings: Settings,
    ) -> None:
        self.sessions = sessions
        self.events = events
        self.settings = settings

    async def balance(self, account_id: UUID, session: AsyncSession | None = None) -> int:
        if session is not None:
            return int(
                await session.scalar(
                    select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
                        CreditLedger.account_id == account_id
                    )
                )
                or 0
            )
        async with self.sessions() as owned:
            return await self.balance(account_id, owned)

    async def transactions(self, account_id: UUID, limit: int = 100) -> list[CreditLedger]:
        async with self.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(CreditLedger)
                        .where(CreditLedger.account_id == account_id)
                        .order_by(CreditLedger.created_at.desc())
                        .limit(limit)
                    )
                ).all()
            )

    async def consume_credits(
        self,
        account_id: UUID,
        user_id: UUID,
        amount: int,
        reference_id: UUID,
        description: str,
    ) -> int:
        changed = False
        async with self.sessions() as session, session.begin():
            processed = await session.scalar(
                select(ProcessedEvent).where(ProcessedEvent.event_id == reference_id)
            )
            if processed is not None:
                return await self.balance(account_id, session)
            current = await self.balance(account_id, session)
            if current < amount:
                raise CreditsError(409, "INSUFFICIENT_CREDITS", "Available credits are insufficient")
            session.add_all([
                CreditLedger(
                    account_id=account_id,
                    entry_type=LedgerType.USAGE,
                    amount=-amount,
                    description=description.strip(),
                    reference_type="usage",
                    reference_id=str(reference_id),
                    created_by_user_id=user_id,
                ),
                ProcessedEvent(event_id=reference_id, event_type="credits.consumed"),
            ])
            changed = True
            remaining = current - amount
        if changed:
            await self._balance_events(account_id, -amount, "debited", str(reference_id))
        return remaining

    async def listings(self) -> list[MarketplaceListing]:
        async with self.sessions() as session, session.begin():
            cutoff = datetime.now(UTC) - timedelta(minutes=15)
            await session.execute(
                update(MarketplaceListing)
                .where(
                    MarketplaceListing.status == ListingStatus.RESERVED,
                    MarketplaceListing.updated_at < cutoff,
                )
                .values(
                    status=ListingStatus.OPEN,
                    buyer_account_id=None,
                    payment_intent_id=None,
                    updated_at=datetime.now(UTC),
                )
            )
            return list(
                (
                    await session.scalars(
                        select(MarketplaceListing)
                        .where(
                            MarketplaceListing.status == ListingStatus.OPEN,
                            MarketplaceListing.expires_at > datetime.now(UTC),
                        )
                        .order_by(MarketplaceListing.created_at.desc())
                    )
                ).all()
            )

    async def create_listing(
        self, account_id: UUID, user_id: UUID, payload: ListingCreate
    ) -> MarketplaceListing:
        async with self.sessions() as session, session.begin():
            balance = await self.balance(account_id, session)
            reserved = int(
                await session.scalar(
                    select(func.coalesce(func.sum(MarketplaceListing.credits), 0)).where(
                        MarketplaceListing.seller_account_id == account_id,
                        MarketplaceListing.status.in_([ListingStatus.OPEN, ListingStatus.RESERVED]),
                        MarketplaceListing.expires_at > datetime.now(UTC),
                    )
                )
                or 0
            )
            if balance - reserved < payload.credits:
                raise CreditsError(409, "INSUFFICIENT_CREDITS", "Available credits are insufficient")
            listing = MarketplaceListing(
                seller_account_id=account_id,
                credits=payload.credits,
                price_cents=payload.price_cents,
                expires_at=datetime.now(UTC) + timedelta(days=payload.expires_in_days),
            )
            session.add(listing)
        del user_id
        return listing

    async def cancel_listing(self, listing_id: UUID, account_id: UUID, superadmin: bool) -> None:
        async with self.sessions() as session, session.begin():
            listing = await session.get(MarketplaceListing, listing_id, with_for_update=True)
            if listing is None:
                raise CreditsError(404, "LISTING_NOT_FOUND", "Marketplace listing was not found")
            if listing.seller_account_id != account_id and not superadmin:
                raise CreditsError(403, "LISTING_ACCESS_DENIED", "You do not own this listing")
            if listing.status != ListingStatus.OPEN:
                raise CreditsError(409, "LISTING_NOT_OPEN", "Only open listings can be canceled")
            listing.status = ListingStatus.CANCELED

    async def reserve_purchase(self, listing_id: UUID, buyer_account_id: UUID) -> MarketplaceListing:
        async with self.sessions() as session, session.begin():
            listing = await session.get(MarketplaceListing, listing_id, with_for_update=True)
            if listing is None:
                raise CreditsError(404, "LISTING_NOT_FOUND", "Marketplace listing was not found")
            expires_at = listing.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if listing.status != ListingStatus.OPEN or expires_at <= datetime.now(UTC):
                raise CreditsError(409, "LISTING_UNAVAILABLE", "Marketplace listing is unavailable")
            if listing.seller_account_id == buyer_account_id:
                raise CreditsError(409, "SELF_PURCHASE_NOT_ALLOWED", "An account cannot buy its own listing")
            listing.status = ListingStatus.RESERVED
            listing.buyer_account_id = buyer_account_id
            return listing

    async def set_payment_intent(self, listing_id: UUID, payment_intent_id: str) -> None:
        async with self.sessions() as session, session.begin():
            listing = await session.get(MarketplaceListing, listing_id, with_for_update=True)
            if listing is None or listing.status != ListingStatus.RESERVED:
                raise CreditsError(409, "LISTING_NOT_RESERVED", "Marketplace listing is not reserved")
            listing.payment_intent_id = payment_intent_id

    async def release_reservation(self, listing_id: UUID, buyer_account_id: UUID | None = None) -> None:
        async with self.sessions() as session, session.begin():
            listing = await session.get(MarketplaceListing, listing_id, with_for_update=True)
            if (
                listing is not None
                and listing.status == ListingStatus.RESERVED
                and (buyer_account_id is None or listing.buyer_account_id == buyer_account_id)
            ):
                listing.status = ListingStatus.OPEN
                listing.buyer_account_id = None
                listing.payment_intent_id = None

    async def complete_purchase(
        self, listing_id: UUID, buyer_account_id: UUID, user_id: UUID, payment_intent_id: str
    ) -> UUID:
        transaction_id = uuid4()
        async with self.sessions() as session, session.begin():
            listing = await session.get(MarketplaceListing, listing_id, with_for_update=True)
            if listing is None:
                raise CreditsError(404, "LISTING_NOT_FOUND", "Marketplace listing was not found")
            if listing.status == ListingStatus.SOLD and listing.payment_intent_id == payment_intent_id:
                existing = await session.scalar(
                    select(CreditLedger).where(
                        CreditLedger.reference_type == "marketplace_purchase",
                        CreditLedger.reference_id == payment_intent_id,
                        CreditLedger.account_id == buyer_account_id,
                    )
                )
                if existing is None:
                    raise CreditsError(409, "TRANSFER_STATE_INVALID", "Transfer state is inconsistent")
                return existing.id
            if (
                listing.status != ListingStatus.RESERVED
                or listing.buyer_account_id != buyer_account_id
                or listing.payment_intent_id != payment_intent_id
            ):
                raise CreditsError(409, "PURCHASE_MISMATCH", "Payment does not match this reservation")
            if await self.balance(listing.seller_account_id, session) < listing.credits:
                raise CreditsError(409, "SELLER_BALANCE_CHANGED", "Seller no longer has enough credits")
            session.add_all([
                CreditLedger(
                    id=transaction_id,
                    account_id=buyer_account_id,
                    entry_type=LedgerType.TRADE,
                    amount=listing.credits,
                    description="Marketplace credit purchase",
                    reference_type="marketplace_purchase",
                    reference_id=payment_intent_id,
                    counterparty_account_id=listing.seller_account_id,
                    created_by_user_id=user_id,
                ),
                CreditLedger(
                    account_id=listing.seller_account_id,
                    entry_type=LedgerType.TRADE,
                    amount=-listing.credits,
                    description="Marketplace credit sale",
                    reference_type="marketplace_sale",
                    reference_id=payment_intent_id,
                    counterparty_account_id=buyer_account_id,
                    created_by_user_id=user_id,
                ),
            ])
            listing.status = ListingStatus.SOLD
        await self._balance_events(buyer_account_id, listing.credits, "credited", str(transaction_id))
        await self._balance_events(
            listing.seller_account_id, -listing.credits, "debited", str(transaction_id)
        )
        return transaction_id

    async def consume(self, envelope: dict[str, Any]) -> None:
        event_id = UUID(str(envelope["event_id"]))
        event_type = str(envelope["event_type"])
        payload = dict(envelope.get("payload") or {})
        correlation_id = str(envelope.get("correlation_id") or event_id)
        changed: tuple[UUID, int, str] | None = None
        async with self.sessions() as session, session.begin():
            if await session.scalar(select(ProcessedEvent.id).where(ProcessedEvent.event_id == event_id)):
                return
            account_id = UUID(str(payload["account_id"]))
            if event_type == "invoice.paid":
                amount = self.settings.plan_grants.get(str(payload.get("plan", "free")).lower(), 0)
                if amount > 0:
                    session.add(
                        CreditLedger(
                            account_id=account_id,
                            entry_type=LedgerType.GRANT,
                            amount=amount,
                            description=f"Credits granted for {payload.get('plan', 'plan')} payment",
                            reference_type="invoice",
                            reference_id=str(payload["invoice_id"]),
                        )
                    )
                    changed = account_id, amount, "credited"
            elif event_type == "credits.purchased":
                amount = int(payload.get("credits", 0))
                if amount > 0:
                    session.add(
                        CreditLedger(
                            account_id=account_id,
                            entry_type=LedgerType.GRANT,
                            amount=amount,
                            description="Credit pack purchase",
                            reference_type="credit_purchase",
                            reference_id=str(payload.get("payment_intent_id") or payload["account_id"]),
                        )
                    )
                    changed = account_id, amount, "credited"
            elif event_type == "refund.issued":
                grant = await session.scalar(
                    select(CreditLedger).where(
                        CreditLedger.account_id == account_id,
                        CreditLedger.entry_type == LedgerType.GRANT,
                        CreditLedger.reference_type == "invoice",
                        CreditLedger.reference_id == str(payload["invoice_id"]),
                    )
                )
                if grant is not None:
                    session.add(
                        CreditLedger(
                            account_id=account_id,
                            entry_type=LedgerType.REFUND_CLAWBACK,
                            amount=-grant.amount,
                            description="Credit grant reversed after refund",
                            reference_type="refund",
                            reference_id=str(payload["refund_id"]),
                        )
                    )
                    changed = account_id, -grant.amount, "debited"
            else:
                raise CreditsError(400, "UNSUPPORTED_EVENT", "Credits Service cannot process this event")
            session.add(ProcessedEvent(event_id=event_id, event_type=event_type))
        if changed:
            await self._balance_events(changed[0], changed[1], changed[2], str(event_id), correlation_id)

    async def _balance_events(
        self,
        account_id: UUID,
        amount: int,
        action: str,
        reference_id: str,
        correlation_id: str = "credits",
    ) -> None:
        balance = await self.balance(account_id)
        payload = {
            "account_id": str(account_id),
            "amount": abs(amount),
            "balance": balance,
            "reference_id": reference_id,
        }
        await self.events.publish(
            EventEnvelope(event_type=f"credits.{action}", correlation_id=correlation_id, payload=payload)
        )
        await self.events.publish(
            EventEnvelope(
                event_type="credits.balance_changed", correlation_id=correlation_id, payload=payload
            )
        )
        if amount < 0 and balance <= self.settings.low_balance_threshold:
            await self.events.publish(
                EventEnvelope(
                    event_type="credits.low_balance", correlation_id=correlation_id, payload=payload
                )
            )
