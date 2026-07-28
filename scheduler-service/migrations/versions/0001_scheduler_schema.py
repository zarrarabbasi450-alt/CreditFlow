"""scheduler schema

Revision ID: 0001_scheduler_schema
Revises:
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_scheduler_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS scheduler")
    op.create_table(
        "scheduled_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("publish_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="scheduled"),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('scheduled', 'cancelled', 'fired', 'failed')",
            name="ck_scheduled_posts_status",
        ),
        schema="scheduler",
    )
    op.create_index(
        "ix_scheduled_posts_account_publish",
        "scheduled_posts",
        ["account_id", "publish_at"],
        schema="scheduler",
    )
    op.create_index(
        "ix_scheduled_posts_due",
        "scheduled_posts",
        ["status", "publish_at"],
        schema="scheduler",
    )
    op.create_index(
        "ix_scheduled_posts_content",
        "scheduled_posts",
        ["content_id"],
        schema="scheduler",
    )


def downgrade() -> None:
    op.drop_index("ix_scheduled_posts_content", table_name="scheduled_posts", schema="scheduler")
    op.drop_index("ix_scheduled_posts_due", table_name="scheduled_posts", schema="scheduler")
    op.drop_index("ix_scheduled_posts_account_publish", table_name="scheduled_posts", schema="scheduler")
    op.drop_table("scheduled_posts", schema="scheduler")
