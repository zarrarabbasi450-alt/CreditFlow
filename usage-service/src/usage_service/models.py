from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, MetaData, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

USAGE_SCHEMA = "usage"


class Base(DeclarativeBase):
    metadata = MetaData(schema=USAGE_SCHEMA)


class UsageLedger(Base):
    __tablename__ = "usage_ledger"
    __table_args__ = (
        CheckConstraint("prompt_tokens >= 0", name="ck_usage_prompt_tokens_nonnegative"),
        CheckConstraint("completion_tokens >= 0", name="ck_usage_completion_tokens_nonnegative"),
        CheckConstraint("total_tokens > 0", name="ck_usage_total_tokens_positive"),
        CheckConstraint("cost_microusd >= 0", name="ck_usage_cost_nonnegative"),
        Index("ix_usage_ledger_account_created", "account_id", "created_at"),
        Index("ix_usage_ledger_account_model", "account_id", "model"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, unique=True)
    generation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, unique=True)
    account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
