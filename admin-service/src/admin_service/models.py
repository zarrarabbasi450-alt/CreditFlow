from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Index, MetaData, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from admin_service.db_types import GUID

ADMIN_SCHEMA = "admin"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(schema=ADMIN_SCHEMA)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_audit_log_event_id"),
        Index("ix_audit_log_account_created", "account_id", "created_at"),
        Index("ix_audit_log_action", "action"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    event_id: Mapped[UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    account_id: Mapped[UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    actor_id: Mapped[UUID | None] = mapped_column(GUID(), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
