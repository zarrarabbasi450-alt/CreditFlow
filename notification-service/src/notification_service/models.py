from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, MetaData, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from notification_service.db_types import GUID

NOTIFICATIONS_SCHEMA = "notifications"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(schema=NOTIFICATIONS_SCHEMA)


class NotificationLog(Base):
    __tablename__ = "notification_log"
    __table_args__ = (
        CheckConstraint("channel IN ('email', 'slack')", name="ck_notification_log_channel"),
        CheckConstraint("status IN ('sent', 'failed', 'skipped')", name="ck_notification_log_status"),
        Index("ix_notification_log_account_created", "account_id", "created_at"),
        Index("ix_notification_log_event_type", "event_type"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    account_id: Mapped[UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    user_id: Mapped[UUID | None] = mapped_column(GUID(), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    recipient: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(240), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProcessedEvent(Base):
    """Idempotency ledger for RabbitMQ-consumed events — a redelivered message with
    an event_id already recorded here is a no-op, never reprocessed (never re-sent)."""

    __tablename__ = "processed_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_notification_processed_event_id"),)

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(GUID(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
