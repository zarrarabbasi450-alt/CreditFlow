from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, Index, MetaData, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

CREDITS_SCHEMA = "credits"


class Base(DeclarativeBase):
    metadata = MetaData(schema=CREDITS_SCHEMA)


class LedgerType(StrEnum):
    GRANT = "grant"
    USAGE = "usage"
    TRADE = "trade"
    REFUND_CLAWBACK = "refund_clawback"
    ADJUSTMENT = "adjustment"


class ListingStatus(StrEnum):
    OPEN = "open"
    RESERVED = "reserved"
    SOLD = "sold"
    CANCELED = "canceled"
    EXPIRED = "expired"


class CreditLedger(Base):
    __tablename__ = "credits_ledger"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_credits_ledger_nonzero_amount"),
        Index("ix_credits_ledger_account_created", "account_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    entry_type: Mapped[LedgerType] = mapped_column(
        Enum(
            LedgerType,
            name="ledger_type",
            schema=CREDITS_SCHEMA,
            values_callable=lambda values: [value.value for value in values],
        )
    )
    amount: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(500))
    reference_type: Mapped[str] = mapped_column(String(64))
    reference_id: Mapped[str] = mapped_column(String(255), index=True)
    counterparty_account_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"
    __table_args__ = (
        CheckConstraint("credits > 0", name="ck_marketplace_positive_credits"),
        CheckConstraint("price_cents > 0", name="ck_marketplace_positive_price"),
        Index("ix_marketplace_status_expires", "status", "expires_at"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    seller_account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    credits: Mapped[int] = mapped_column(BigInteger)
    price_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[ListingStatus] = mapped_column(
        Enum(
            ListingStatus,
            name="listing_status",
            schema=CREDITS_SCHEMA,
            values_callable=lambda values: [value.value for value in values],
        ),
        default=ListingStatus.OPEN,
    )
    buyer_account_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_credits_processed_event_id"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(255), index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
