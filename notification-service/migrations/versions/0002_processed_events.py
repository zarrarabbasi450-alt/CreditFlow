"""Add processed_events idempotency ledger for RabbitMQ-consumed events.

Revision ID: 0002_processed_events
Revises: 0001_notification_schema
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_processed_events"
down_revision: str | None = "0001_notification_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", name="uq_notification_processed_event_id"),
        schema="notifications",
    )
    op.create_index(
        "ix_notification_processed_events_event_type",
        "processed_events",
        ["event_type"],
        schema="notifications",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_processed_events_event_type", table_name="processed_events", schema="notifications"
    )
    op.drop_table("processed_events", schema="notifications")
