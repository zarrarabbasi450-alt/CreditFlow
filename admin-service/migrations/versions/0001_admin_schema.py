"""admin schema

Revision ID: 0001_admin_schema
Revises:
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_admin_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS admin")
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("payload", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("event_id", name="uq_audit_log_event_id"),
        schema="admin",
    )
    op.create_index("ix_audit_log_event_id", "audit_log", ["event_id"], schema="admin")
    op.create_index("ix_audit_log_account_id", "audit_log", ["account_id"], schema="admin")
    op.create_index(
        "ix_audit_log_account_created", "audit_log", ["account_id", "created_at"], schema="admin"
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action"], schema="admin")


def downgrade() -> None:
    op.drop_table("audit_log", schema="admin")
