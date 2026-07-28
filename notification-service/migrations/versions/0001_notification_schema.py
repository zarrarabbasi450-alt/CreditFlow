"""notification schema

Revision ID: 0001_notification_schema
Revises:
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_notification_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS notifications")
    op.create_table(
        "notification_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=True),
        sa.Column("subject", sa.String(240), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("provider_message_id", sa.String(240), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("channel IN ('email', 'slack')", name="ck_notification_log_channel"),
        sa.CheckConstraint("status IN ('sent', 'failed', 'skipped')", name="ck_notification_log_status"),
        schema="notifications",
    )
    op.create_index(
        "ix_notification_log_account_id", "notification_log", ["account_id"], schema="notifications"
    )
    op.create_index(
        "ix_notification_log_account_created",
        "notification_log",
        ["account_id", "created_at"],
        schema="notifications",
    )
    op.create_index(
        "ix_notification_log_event_type", "notification_log", ["event_type"], schema="notifications"
    )


def downgrade() -> None:
    op.drop_table("notification_log", schema="notifications")
