"""Add processed_events idempotency ledger for RabbitMQ-consumed events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_processed_events"
down_revision: str | None = "0003_invites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_tenant_processed_event_id"),
        schema="tenant",
    )
    op.create_index(
        "ix_tenant_processed_events_event_type", "processed_events", ["event_type"], schema="tenant"
    )


def downgrade() -> None:
    op.drop_table("processed_events", schema="tenant")
