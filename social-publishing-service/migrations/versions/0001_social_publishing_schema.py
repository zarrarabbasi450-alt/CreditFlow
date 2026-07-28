"""social publishing schema

Revision ID: 0001_social_schema
Revises:
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_social_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS social")
    op.create_table(
        "social_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="linkedin"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("profile_urn", sa.String(160), nullable=True),
        sa.Column("profile_name", sa.String(240), nullable=True),
        sa.Column("profile_email", sa.String(320), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("oauth_state", sa.String(160), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False, server_default=""),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("provider IN ('linkedin')", name="ck_social_connections_provider"),
        sa.CheckConstraint(
            "status IN ('pending', 'connected', 'expired', 'revoked')",
            name="ck_social_connections_status",
        ),
        schema="social",
    )
    op.create_index(
        "ix_social_connections_account_provider",
        "social_connections",
        ["account_id", "provider"],
        schema="social",
    )
    op.create_index(
        "ix_social_connections_oauth_state", "social_connections", ["oauth_state"], schema="social"
    )
    op.create_table(
        "publish_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheduled_post_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_asset_ref", sa.Text(), nullable=True),
        sa.Column("linkedin_post_id", sa.String(240), nullable=True),
        sa.Column("linkedin_post_url", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('queued', 'publishing', 'published', 'failed', 'dead_letter')",
            name="ck_publish_jobs_status",
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["social.social_connections.id"], ondelete="SET NULL"),
        schema="social",
    )
    op.create_index(
        "ix_publish_jobs_account_status", "publish_jobs", ["account_id", "status"], schema="social"
    )
    op.create_index("ix_publish_jobs_scheduled_post", "publish_jobs", ["scheduled_post_id"], schema="social")
    op.create_table(
        "post_media",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("publish_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("image_asset_ref", sa.Text(), nullable=True),
        sa.Column("linkedin_asset_urn", sa.String(240), nullable=True),
        sa.Column("upload_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["publish_job_id"], ["social.publish_jobs.id"], ondelete="CASCADE"),
        schema="social",
    )
    op.create_index("ix_post_media_job", "post_media", ["publish_job_id"], schema="social")


def downgrade() -> None:
    op.drop_index("ix_post_media_job", table_name="post_media", schema="social")
    op.drop_table("post_media", schema="social")
    op.drop_index("ix_publish_jobs_scheduled_post", table_name="publish_jobs", schema="social")
    op.drop_index("ix_publish_jobs_account_status", table_name="publish_jobs", schema="social")
    op.drop_table("publish_jobs", schema="social")
    op.drop_index("ix_social_connections_oauth_state", table_name="social_connections", schema="social")
    op.drop_index("ix_social_connections_account_provider", table_name="social_connections", schema="social")
    op.drop_table("social_connections", schema="social")
