"""content schema

Revision ID: 0001_content_schema
Revises:
Create Date: 2026-07-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_content_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS content")
    op.create_table(
        "content",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=40), nullable=False, server_default="post"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_asset_ref", sa.Text(), nullable=True),
        sa.Column("source_generation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version >= 1", name="ck_content_version_positive"),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'published')",
            name="ck_content_status",
        ),
        schema="content",
    )
    op.create_table(
        "content_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content.content.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_asset_ref", sa.Text(), nullable=True),
        sa.Column("edited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("content_id", "version", name="uq_content_versions_content_version"),
        schema="content",
    )
    op.create_index("ix_content_account_status", "content", ["account_id", "status"], schema="content")
    op.create_index("ix_content_account_updated", "content", ["account_id", "updated_at"], schema="content")
    op.create_index(
        "ix_content_versions_content_created",
        "content_versions",
        ["content_id", "created_at"],
        schema="content",
    )


def downgrade() -> None:
    op.drop_index("ix_content_versions_content_created", table_name="content_versions", schema="content")
    op.drop_index("ix_content_account_updated", table_name="content", schema="content")
    op.drop_index("ix_content_account_status", table_name="content", schema="content")
    op.drop_table("content_versions", schema="content")
    op.drop_table("content", schema="content")
    op.execute("DROP SCHEMA IF EXISTS content")
