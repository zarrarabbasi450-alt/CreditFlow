from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, MetaData, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEDULER_SCHEMA = "scheduler"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEDULER_SCHEMA)


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'cancelled', 'fired', 'failed')", name="ck_scheduled_posts_status"
        ),
        Index("ix_scheduled_posts_account_publish", "account_id", "publish_at"),
        Index("ix_scheduled_posts_due", "status", "publish_at"),
        Index("ix_scheduled_posts_content", "content_id"),
        Index(
            "uq_scheduled_posts_active_content",
            "account_id",
            "content_id",
            unique=True,
            postgresql_where=text("status = 'scheduled'"),
            sqlite_where=text("status = 'scheduled'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    content_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class ProcessedEvent(Base):
    """Idempotency ledger for RabbitMQ-consumed events — a redelivered message with
    an event_id already recorded here is a no-op, never reprocessed."""

    __tablename__ = "processed_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_scheduler_processed_event_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
