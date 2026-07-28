from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SOCIAL_SCHEMA = "social"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(schema=SOCIAL_SCHEMA)


class SocialConnection(Base):
    __tablename__ = "social_connections"
    __table_args__ = (
        CheckConstraint("provider IN ('linkedin')", name="ck_social_connections_provider"),
        CheckConstraint(
            "status IN ('pending', 'connected', 'expired', 'revoked', 'failed')",
            name="ck_social_connections_status",
        ),
        Index("ix_social_connections_account_provider", "account_id", "provider"),
        Index("ix_social_connections_oauth_state", "oauth_state"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="linkedin")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    profile_urn: Mapped[str | None] = mapped_column(String(160), nullable=True)
    profile_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    profile_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    oauth_state: Mapped[str | None] = mapped_column(String(160), nullable=True)
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class PublishJob(Base):
    __tablename__ = "publish_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'publishing', 'published', 'failed', 'dead_letter')",
            name="ck_publish_jobs_status",
        ),
        Index("ix_publish_jobs_account_status", "account_id", "status"),
        Index("ix_publish_jobs_scheduled_post", "scheduled_post_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    content_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    scheduled_post_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{SOCIAL_SCHEMA}.social_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_asset_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_post_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    linkedin_post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class PostMedia(Base):
    __tablename__ = "post_media"
    __table_args__ = (Index("ix_post_media_job", "publish_job_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    publish_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey(f"{SOCIAL_SCHEMA}.publish_jobs.id", ondelete="CASCADE"), nullable=False
    )
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    image_asset_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_asset_urn: Mapped[str | None] = mapped_column(String(240), nullable=True)
    upload_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProcessedEvent(Base):
    """Idempotency ledger for RabbitMQ-consumed events — a redelivered message with
    an event_id already recorded here is a no-op, never reprocessed (never a duplicate
    LinkedIn post)."""

    __tablename__ = "processed_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_social_processed_event_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
