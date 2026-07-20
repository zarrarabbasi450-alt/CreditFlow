from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    MetaData,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

BILLING_SCHEMA = "billing"


class Base(DeclarativeBase):
    metadata = MetaData(schema=BILLING_SCHEMA)


class Plan(StrEnum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("plan IN ('free','pro','team','enterprise')", name="ck_billing_subscription_plan"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(unique=True, index=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    stripe_subscription_item_id: Mapped[str | None] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(32), default=Plan.FREE, server_default=Plan.FREE)
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active")
    seats: Mapped[int] = mapped_column(default=1, server_default="1")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(index=True)
    stripe_invoice_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    number: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3))
    amount_due: Mapped[int] = mapped_column(BigInteger)
    amount_paid: Mapped[int] = mapped_column(BigInteger)
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), index=True)
    hosted_invoice_url: Mapped[str | None] = mapped_column(Text)
    invoice_pdf: Mapped[str | None] = mapped_column(Text)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubscriptionEvent(Base):
    __tablename__ = "subscription_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(255), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(index=True)
    invoice_id: Mapped[UUID] = mapped_column(index=True)
    stripe_refund_id: Mapped[str] = mapped_column(String(255), unique=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    reason: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_billing_outbox_unpublished", "published_at", "created_at"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(255), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    correlation_id: Mapped[str] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
